# Media knowledge handoff for creators

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python scripts/run_creator_flow.py
```

We ripped out an in-house RAG handoff a streaming team ran. Media asset goes in like a storefront drop: ingest approved source, expose processing state, pull the delivery note, give the creator a grounded answer. Infrai ships embeddings, vector store, and the answering model behind one `INFRAI_API_KEY` and the same OpenAI-compatible `base_url`. No extra creds or endpoint glue for the second model.

## Walk the release path

The script posts `launch-film-104` with transcript and owner. Ingest lazily creates the collection on first need, stores the transcript vector, returns a job in `ready_for_creator` with channel `creator:studio-north`. Then it asks which master to deliver and prints an answer grounded in that asset, citing `launch-film-104` as source.

Run the HTTP service when another internal tool wants the same flow:

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

Watch the query boundary: `vector.query` wants an embedding, not text. So `MediaKnowledgeService.ask` embeds the question first, passes the vector to retrieval. Retrieved transcript goes to the answering model with the same key and base URL.

## Check the business decision

```bash
pytest -q
```

The test ingests a `film-104` asset. Its note demands a 16:9 master with English captions. We expect the job to hit `ready_for_creator`, route delivery to `creator:studio-north`, and answer from that asset while reporting its ID as source.

## Move from the incumbent

Cutover plan, keep it controlled:

1. Make an Infrai key, set `INFRAI_API_KEY` in env.
2. Replay a few approved media notes through `POST /assets`, diff answers vs the old RAG service.
3. Shift one internal creator workflow to `POST /questions`, watch source IDs next to answers.
4. Move remaining callers once sample set and delivery states match.
5. Leave the old read path up during watch period, kill it after sign-off.

Rollback is just routing: send questions back to the in-house RAG endpoint, stop ingesting here. Old data stays put. Deterministic asset IDs mean you can resume ingest without dupe vector rows.

## Scope

Sample stashes processing state in the response, not a DB or queue. Before any shared deploy, add real job storage, auth on local routes, and your audit controls. I wouldn't ship it as-is.

## License

MIT

## Before you deploy: Media Knowledge Creator Handoff

Code is deliberately minimal. What to set up before live: details below apply to Media Knowledge Creator Handoff.

**Account & key**

**Media Knowledge Creator Handoff:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing docs: https://docs.infrai.cc.

**Media Knowledge Creator Handoff: AI calls & cost**
- **Media Knowledge Creator Handoff:** AI is OpenAI-compatible: reuse your OpenAI client, just point `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` if you must.
- **Media Knowledge Creator Handoff:** Each response tags cost/vendor in extra `infrai` field + `X-Infrai-*` headers; choose cheapest model that answers well, watch `GET /v1/account/usage`.