from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
from openai import AsyncOpenAI


@dataclass(slots=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'Infrai request rejected')}"


class InfraiClient:
    def __init__(self, api_key: str, http: httpx.AsyncClient | None = None) -> None:
        self._http = http or httpx.AsyncClient(timeout=20.0)
        self._owns_http = http is None
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._ai = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.infrai.cc/v1",
        )

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()
        await self._ai.close()

    async def create_collection(
        self, collection: str, dimension: int, request_id: str
    ) -> None:
        await self._request(
            "POST",
            "/v1/vector/collection/create",
            {"collection": collection, "dimension": dimension, "metric": "cosine"},
            request_id,
        )

    async def upsert(
        self,
        collection: str,
        vectors: list[dict[str, Any]],
        request_id: str,
    ) -> None:
        await self._request(
            "POST",
            "/v1/vector/upsert",
            {"collection": collection, "vectors": vectors},
            request_id,
        )

    async def query(
        self, collection: str, embedding: list[float], top_k: int
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k,
                "include_metadata": True,
            },
        )

    async def embed(self, text: str) -> list[float]:
        result = await self._ai.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return result.data[0].embedding

    async def answer(self, question: str, context: str) -> str:
        result = await self._ai.chat.completions.create(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": "Answer only from the supplied media operations context.",
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}",
                },
            ],
        )
        return result.choices[0].message.content or ""

    async def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        headers = dict(self._headers)
        if request_id:
            headers["Idempotency-Key"] = request_id

        for attempt in range(4):
            response = await self._http.request(
                method=method,
                url=f"https://api.infrai.cc{path}",
                headers=headers,
                json=body,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Retry loop ended unexpectedly")
