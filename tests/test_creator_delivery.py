from __future__ import annotations

import asyncio
from typing import Any

from media_kb.service import (
    AssetIngestRequest,
    JobState,
    KnowledgeQuestion,
    MediaKnowledgeService,
)


class FakeKnowledgeBackend:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def create_collection(self, collection: str, dimension: int, request_id: str) -> None:
        assert dimension == 3

    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def upsert(self, collection: str, vectors: list[dict[str, Any]], request_id: str) -> None:
        self.saved = vectors

    async def query(self, collection: str, embedding: list[float], top_k: int) -> dict[str, Any]:
        return {"matches": self.saved[:top_k]}

    async def answer(self, question: str, context: str) -> str:
        assert "16:9 master" in context
        return "Deliver the 16:9 master with English captions."


def test_approved_asset_becomes_creator_delivery_and_answers_from_context() -> None:
    asyncio.run(_check_creator_delivery())


async def _check_creator_delivery() -> None:
    service = MediaKnowledgeService(FakeKnowledgeBackend())

    job = await service.ingest(
        AssetIngestRequest(
            asset_id="film-104",
            title="Launch delivery notes",
            transcript="Use the 16:9 master with English captions.",
            creator_id="studio-north",
        )
    )
    answer = await service.ask(KnowledgeQuestion(question="What should be delivered?"))

    assert job.state is JobState.READY_FOR_CREATOR
    assert job.delivery_channel == "creator:studio-north"
    assert answer.source_asset_ids == ["film-104"]
    assert answer.answer == "Deliver the 16:9 master with English captions."
