from __future__ import annotations

import asyncio
import os

from media_kb.infrai import InfraiClient
from media_kb.service import AssetIngestRequest, KnowledgeQuestion, MediaKnowledgeService


async def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running the creator flow")

    client = InfraiClient(api_key)
    service = MediaKnowledgeService(client)
    try:
        job = await service.ingest(
            AssetIngestRequest(
                asset_id="launch-film-104",
                title="Autumn launch delivery notes",
                transcript=(
                    "The storefront launch film is approved for the home page. "
                    "Creators should deliver the 16:9 master with English captions."
                ),
                creator_id="studio-north",
            )
        )
        reply = await service.ask(
            KnowledgeQuestion(question="Which master and captions should the creator deliver?")
        )
        print(job.model_dump_json(indent=2))
        print(reply.model_dump_json(indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
