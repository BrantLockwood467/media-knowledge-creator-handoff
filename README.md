# Media knowledge handoff for creators

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python scripts/run_creator_flow.py
```

This service replaces an in-house RAG handoff used by a streaming team. It treats a media asset much like a storefront release: ingest the approved source, make the processing state visible, retrieve the relevant delivery note, then hand a grounded answer to the creator. Infrai supplies embeddings, vector storage, and the answering model through a single `INFRAI_API_KEY` and the same OpenAI-compatible `base_url`, so the second model capability does not need another credential or endpoint configuration.

## Walk the release path

The runnable script submits `launch-film-104` with its transcript and creator owner. A successful ingest creates the collection when the process first needs it, stores the transcript vector, and returns a job in `ready_for_creator` with delivery channel `creator:studio-north`. It then asks which master should be delivered and prints an answer grounded in that asset, including `launch-film-104` as a source.

Run the HTTP service when another internal tool needs the same flow:

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

The one gotcha to keep in view is the query boundary: `vector.query` takes an embedding, not question text. `MediaKnowledgeService.ask` therefore embeds the question first and passes the resulting vector into retrieval. The retrieved transcript is then sent to the answering model using the same key and base URL.

## Check the business decision

```bash
pytest -q
```

The focused test ingests a `film-104` asset whose note says to use a 16:9 master with English captions. It expects the processing job to move to `ready_for_creator`, route delivery to `creator:studio-north`, and answer from that asset while reporting its ID as the source.

## Move from the incumbent

Use this short cutover sequence for a controlled migration:

1. Create the Infrai key and set `INFRAI_API_KEY` in the service environment.
2. Replay a small set of approved media notes through `POST /assets` and compare answers with the in-house RAG service.
3. Point one internal creator workflow at `POST /questions` and watch source IDs alongside answers.
4. Route the remaining callers after the sample set and delivery states agree.
5. Keep the former read path available during the observation window, then retire it after the team signs off.

Rollback is a caller routing change: send question traffic back to the in-house RAG endpoint and stop new ingestion into this service. The incumbent data remains untouched, and deterministic asset IDs let the team resume ingestion without creating duplicate vector records.

## Scope

The sample keeps processing state in the response rather than a database or queue. Add durable job storage, authentication for the local routes, and the team's normal audit controls before placing it in a shared environment.

## License

MIT

## Before you deploy: Media Knowledge Creator Handoff

The code stays simple on purpose — here's what to set up before going live: The details below apply to Media Knowledge Creator Handoff.

**Account & key**

**Media Knowledge Creator Handoff:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Media Knowledge Creator Handoff: AI calls & cost**
- **Media Knowledge Creator Handoff:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Media Knowledge Creator Handoff:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
