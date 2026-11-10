# Harbourline Assistant POC

Fictional local banking assistant for an interview demonstration. The customer talks. Balances come from SQLite. Product answers come from approved sample pages. A personal loan is collected in conversation and becomes a typed `poc-loan-v1` document. It is submitted only after the customer confirms that document with a demo PIN.

This is not a real bank, not a credit offer, and not a production ledger.

## For the interviewer

| Document | Path |
| --- | --- |
| Install, run, demo, reset, and troubleshooting | [docs/how-to-run.md](docs/how-to-run.md) |
| Architecture, dotted diagram, sequences, ADR | [docs/architecture.md](docs/architecture.md) |
| Click-by-click demo | [docs/demo-script.md](docs/demo-script.md) |
| Interview narrative | [docs/interview-narrative.md](docs/interview-narrative.md) |
| Swagger | http://127.0.0.1:8000/docs after the API is started. OpenAPI JSON is http://127.0.0.1:8000/openapi.json. There is no checked-in Swagger file. |

The dotted architecture is section 6 of `docs/architecture.md`.

The repository originally had no three-form schema. `poc-loan-v1` in `backend/app/domain/contract.py` is the labelled stand-in.

## Measured on this workspace

`cd backend && .venv/bin/python -m pytest tests -q --tb=line`

- 22 tests passed in 1.02s
- Intent labels on the 30-phrase set in `backend/tests/test_rag.py`: 30/30
- Retrieval outcomes on the 13-question set: 13/13

These are the checked-in POC sets, not a production benchmark. Ollama is not installed here, so `BANK_LLM_PROVIDER` stays `deterministic`. Qwen2.5 3B Instruct was not scored.

## Requirements

- Python 3.12
- Node.js 20 or 22, with npm
- No API key

## Install

From the repository root:

```bash
uv python install 3.12
uv venv --python 3.12 backend/.venv
uv pip install -r backend/requirements.txt --python backend/.venv/bin/python
cd frontend && npm install
```

If Python 3.12 is already installed, `python3.12 -m venv backend/.venv` and `backend/.venv/bin/python -m pip install -r backend/requirements.txt` replace the `uv` lines.

## Run

Terminal A:

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal B:

```bash
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. The UI proxies `/api` to port 8000. Confirm the API with http://127.0.0.1:8000/api/health.

## Demo sign-in

Click a demo customer, then **Sign in**.

| Customer | Email | Password | PIN |
| --- | --- | --- | --- |
| Priya Sharma | priya.sharma@example.com | demo-pass-priya | 2580 |
| Arjun Mehta | arjun.mehta@example.com | demo-pass-arjun | 1470 |
| Demo Reviewer | reviewer@harbourline.example | demo-pass-reviewer | — |

Priya, savings ending 4582: available ₹1,25,000. Priya, current ending 9081: available ₹42,500. Arjun, savings ending 2210: available ₹8,750.

A full script, including the salary-slip upload and the reviewer path, is in [docs/how-to-run.md](docs/how-to-run.md). To start from an empty seed, stop the API and run `rm -rf backend/data`.

## Optional Docker

Not part of the recorded test run:

```bash
docker compose up --build
```

The UI is then http://127.0.0.1:8080.

## Limits

- SQLite is a single-writer POC store, not a core banking ledger.
- Sign-in is a labelled demo password, not a bank identity provider.
- Extraction reads text and PDF text layers. Photographs are rejected.
- Embeddings are a local hashed stand-in behind `HybridKnowledgeRetriever`.
- A home loan can be explained from the approved pages. It cannot be submitted.
