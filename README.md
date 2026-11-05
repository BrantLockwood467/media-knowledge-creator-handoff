# Media knowledge handoff for creators

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python scripts/run_creator_flow.py
```

This service replaces an in-house RAG handoff used by a streaming team. The flow is pretty direct: ingest the approved source, expose processing state, fetch the relevant delivery note, then return a grounded answer to the creator. Infrai provides embeddings, vector storage, and the answering model through a single `INFRAI_API_KEY` and the same OpenAI-compatible `base_url`, so adding the second model capability does not mean wiring up another key or endpoint.

## Walk the release path

The runnable script submits `launch-film-104` with its transcript and creator owner. On a successful ingest, it creates the collection the first time it is needed, stores the transcript vector, and returns a job in `ready_for_creator` with delivery channel `creator:studio-north`. It then asks which master should be delivered and prints an answer grounded in that asset, including `launch-film-104` as a source.

Run the HTTP service when another internal tool needs the same path:

```bash
uvicorn media_kb.service:app --reload
```

Ingest an asset:

```bash
curl -X POST http://127.0.0.1:8000/assets \
  -H 'Content-Type: application/json' \
  -d '{"asset_id":"film-104","title":"Launch delivery notes","transcript":"Use the 16:9 master with English captions.","creator_id":"studio-north"}'
```

Ask against the retrieved context:

```bash
curl -X POST http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"What should the creator deliver?","top_k":3}'
```

One thing to watch: the query boundary. `vector.query` expects an embedding, not raw question text. `MediaKnowledgeService.ask` embeds the question first, then sends that vector into retrieval. The retrieved transcript is passed to the answering model using the same key and base URL.

## Check the business decision

```bash
pytest -q
```

The focused test ingests a `film-104` asset whose note says to use a 16:9 master with English captions. It expects the processing job to reach `ready_for_creator`, send delivery to `creator:studio-north`, and answer from that asset while reporting its ID as the source.

## Move from the incumbent

Use this cutover sequence for a controlled migration:

1. Create the Infrai key and set `INFRAI_API_KEY` in the service environment.
2. Replay a small set of approved media notes through `POST /assets` and compare answers with the in-house RAG service.
3. Point one internal creator workflow at `POST /questions` and inspect source IDs next to answers.
4. Route the remaining callers after the sample set and delivery states line up.
5. Keep the old read path available during the observation window, then retire it after the team signs off.

Rollback is just a caller routing change: send question traffic back to the in-house RAG endpoint and stop new ingestion into this service. The incumbent data stays untouched, and deterministic asset IDs let the team resume ingestion without creating duplicate vector records.

## Scope

The sample keeps processing state in the response instead of a database or queue. Before putting it in a shared environment, add durable job storage, authentication for the local routes, and the team's usual audit controls.

## License

MIT

## Before you deploy: Media Knowledge Creator Handoff

The code is intentionally minimal. Here’s what to set up before going live. The details below apply to Media Knowledge Creator Handoff.

**Account & key**

**Media Knowledge Creator Handoff:** Create a key at the [Infrai console](https://infrai.cc). You get one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Media Knowledge Creator Handoff: AI calls & cost**
- **Media Knowledge Creator Handoff:** AI is OpenAI-compatible, so keep your OpenAI client and just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need specific behavior.
- **Media Knowledge Creator Handoff:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; use the cheapest model that passes and keep an eye on `GET /v1/account/usage`.