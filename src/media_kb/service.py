from __future__ import annotations

import os
from enum import StrEnum
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai import InfraiClient, InfraiError


COLLECTION = "media-operations"


class JobState(StrEnum):
    PROCESSING = "processing"
    READY_FOR_CREATOR = "ready_for_creator"


class AssetIngestRequest(BaseModel):
    asset_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    transcript: str = Field(min_length=1)
    creator_id: str = Field(min_length=1)


class ProcessingJob(BaseModel):
    job_id: str
    asset_id: str
    state: JobState
    delivery_channel: str | None = None


class KnowledgeQuestion(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


class KnowledgeAnswer(BaseModel):
    answer: str
    source_asset_ids: list[str]


class MediaKnowledgeService:
    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self._collection_ready = False

    async def ingest(self, asset: AssetIngestRequest) -> ProcessingJob:
        embedding = await self.backend.embed(asset.transcript)
        if not self._collection_ready:
            await self.backend.create_collection(
                COLLECTION, len(embedding), f"collection-{COLLECTION}"
            )
            self._collection_ready = True

        job_id = f"job_{uuid4().hex}"
        await self.backend.upsert(
            COLLECTION,
            [
                {
                    "id": asset.asset_id,
                    "values": embedding,
                    "metadata": {
                        "asset_id": asset.asset_id,
                        "title": asset.title,
                        "content": asset.transcript,
                        "creator_id": asset.creator_id,
                    },
                }
            ],
            request_id=f"ingest-{asset.asset_id}",
        )
        return ProcessingJob(
            job_id=job_id,
            asset_id=asset.asset_id,
            state=JobState.READY_FOR_CREATOR,
            delivery_channel=f"creator:{asset.creator_id}",
        )

    async def ask(self, request: KnowledgeQuestion) -> KnowledgeAnswer:
        question_vector = await self.backend.embed(request.question)
        result = await self.backend.query(COLLECTION, question_vector, request.top_k)
        matches = result.get("matches", [])
        context = "\n\n".join(
            str(item.get("metadata", {}).get("content", "")) for item in matches
        )
        answer = await self.backend.answer(request.question, context)
        source_ids = [
            str(item.get("metadata", {}).get("asset_id", item.get("id", "")))
            for item in matches
        ]
        return KnowledgeAnswer(answer=answer, source_asset_ids=source_ids)


def create_app(service: MediaKnowledgeService | None = None) -> FastAPI:
    active_service = service

    def get_service() -> MediaKnowledgeService:
        nonlocal active_service
        if active_service is not None:
            return active_service
        api_key = os.environ.get("INFRAI_API_KEY")
        if not api_key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        active_service = MediaKnowledgeService(InfraiClient(api_key))
        return active_service

    app = FastAPI(title="Media knowledge delivery")

    @app.post("/assets", response_model=ProcessingJob, status_code=201)
    async def ingest_asset(asset: AssetIngestRequest) -> ProcessingJob:
        try:
            return await get_service().ingest(asset)
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(status_code=status, detail=exc.detail) from exc

    @app.post("/questions", response_model=KnowledgeAnswer)
    async def answer_question(question: KnowledgeQuestion) -> KnowledgeAnswer:
        try:
            return await get_service().ask(question)
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(status_code=status, detail=exc.detail) from exc

    return app


app = create_app()
