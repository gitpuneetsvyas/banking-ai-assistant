# How to run the Harbourline Assistant

This is the document to follow when reviewing or demonstrating the POC. All customers, balances, and policy pages are fictional. The assistant is not a real bank and SQLite is not a core ledger.

## 1. Documents in this submission

| What you need | Where it is |
| --- | --- |
| How to install, run, test, and reset | This file, and the shorter copy in `README.md` |
| Architecture, dotted diagram, trust boundaries, ADR | `docs/architecture.md` |
| Ten-minute click path | `docs/demo-script.md` |
| First-person interview explanation | `docs/interview-narrative.md` |
| Swagger UI and OpenAPI | Not a file in the repo. Start the API, then open http://127.0.0.1:8000/docs. The raw contract is http://127.0.0.1:8000/openapi.json |
| Loan contract the conversation fills | `backend/app/domain/contract.py` (`poc-loan-v1`) |
| Fictional policy figures | `backend/app/domain/policy.py` and `backend/knowledge/` |
| Sample salary slips | `backend/samples/priya_salary_slip.txt` and `backend/samples/priya_salary_slip_conflict.txt` |

Section 6 of `docs/architecture.md` is the mobile-friendly dotted architecture. Sections 5 and 7 are the Mermaid system diagram and the LangGraph loan diagram.

## 2. What has to be installed

- Python 3.12. The pinned backend in `backend/requirements.txt` was installed and tested on 3.12.
- Node.js 20 or 22, with `npm`. The UI was built with Node 22 and Vite 5.
- A browser on the same machine.

`uv` is the reliable way to get Python 3.12 when the system Python is older. Docker is optional and was not part of the verified test run.

No API key is required. The default model setting is `deterministic`, so the demo does not call Ollama or any hosted model.

## 3. Install the backend

From the repository root:

```bash
uv python install 3.12
uv venv --python 3.12 backend/.venv
uv pip install -r backend/requirements.txt --python backend/.venv/bin/python
```

If `python3.12` is already on your `PATH`, this is equivalent:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

Copy the sample environment file if you want the variables visible. The defaults in code match this file, so the copy is optional:

```bash
cp .env.example .env
```

Settings use the `BANK_` prefix. The database file is created at `backend/data/bank.db` the first time the API starts. That directory is gitignored.

## 4. Install the frontend

```bash
cd frontend
npm install
```

`frontend/vite.config.ts` proxies `/api` to `http://127.0.0.1:8000` and serves the UI on port 5173.

## 5. Run it

Use two terminals. Start the API first.

Terminal A, from `backend/`:

```bash
.venv/bin/python -m pytest
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Pytest should report the suite passed before you demo. The last recorded run in this workspace was **22 passed in 1.02s**. On the checked-in sets in `backend/tests/test_rag.py`, intent labelling is 30/30 and retrieval outcomes are 13/13. Those sets are the POC evaluation, not a production benchmark.

Terminal B, from `frontend/`:

```bash
npm run dev
```

Then open:

| Surface | URL |
| --- | --- |
| Customer and reviewer UI | http://127.0.0.1:5173 |
| Health | http://127.0.0.1:8000/api/health |
| Swagger UI | http://127.0.0.1:8000/docs |
| OpenAPI JSON | http://127.0.0.1:8000/openapi.json |

Health returns `"status": "ok"`, `"fictional": true`, and `"llm_provider": "deterministic"`.

Stop either process with Ctrl+C in its terminal.

## 6. Sign in

The login screen has three demo buttons. Click one, then click **Sign in**. Passwords are labelled demo passwords.

| Who | Email | Password | PIN | Use them for |
| --- | --- | --- | --- | --- |
| Priya Sharma | priya.sharma@example.com | demo-pass-priya | 2580 | Two accounts, the loan demo |
| Arjun Mehta | arjun.mehta@example.com | demo-pass-arjun | 1470 | A different customer's balance |
| Demo Reviewer | reviewer@harbourline.example | demo-pass-reviewer | none | The review queue |

Priya's available savings balance is ₹1,25,000 (account ending 4582). Her current account, ending 9081, has ₹42,500 available. Arjun's only savings account ends 2210 and has ₹8,750 available. The ledger balance is a different column and is not spoken as the available balance.

## 7. Demonstration sequence

A previous run may already have an open draft for Priya. Only one open draft is allowed. If the panel says the application is paused or still collecting, type `cancel this application` before starting again. For a completely fresh seed, use the reset in section 8 while the API is stopped.

### Balance

Sign in as Priya.

1. Send `What is my bank balance?`
2. The assistant must ask which account: savings ending 4582 or current ending 9081.
3. Send `Savings`.
4. The reply is the available savings balance ₹1,25,000, account ending 4582. The tool trace names `get_account_balance`.

### Approved product page

Send `What documents are needed for a personal loan?`

The answer cites `DOC-PL-DOCS`. It does not open a form.

### Formless personal loan

Send `I want to apply for a ₹5 lakh loan`, then one message at a time:

1. `Yes` — consent. The card fills her name from KYC. She does not type her address.
2. `Salaried`
3. `Northwind Analytics`
4. `80000`
5. `36 months`
6. `Home renovation`
7. Click **Upload document** and choose `backend/samples/priya_salary_slip.txt`.

The card moves to **Ready for your confirmation**. The amount is ₹5,00,000, tenure 36 months, income ₹80,000, schema `poc-loan-v1`. Enter PIN `2580` in the Transaction PIN box and click **Confirm and submit**. The reference looks like `HB-PL-0001`. A second confirmation returns the same reference.

The PIN box is the confirmation control. The customer never edits the application fields.

### Another customer

Sign out. Sign in as Arjun. Send `What is my savings balance?`

The reply is ₹8,750, account ending 2210. It does not mention Priya's ₹1,25,000.

### Abstention and a product clarification

Send `What is the policy on cryptocurrency trading credit lines?`

The assistant says it has no approved page and does not invent a rate.

Send `What documents do I need for a loan?`

The assistant asks whether you mean a personal loan or a home loan.

### Human review

This needs a draft that is not already submitted. Reset with section 8, or cancel any open draft, then repeat the loan messages above but upload `backend/samples/priya_salary_slip_conflict.txt`. That slip says INR 50,000 against the stated ₹80,000.

The panel changes to **Paused for a reviewer**. The PIN does not submit.

Sign out, sign in as Demo Reviewer, and click **Approve** on Priya's card. Sign back in as Priya. The draft is waiting for confirmation. PIN `2580` submits it.

## 8. Reset the fictional database

Stop the API first. From the repository root:

```bash
rm -rf backend/data
```

Start the API again. The seed loads because the customer table is empty. Uploaded files and generated PDFs live under `backend/data/` and are removed with it.

Five wrong PINs lock confirmation for that draft. A reset is the way back.

## 9. Tests

From `backend/`:

```bash
.venv/bin/python -m pytest tests -q --tb=line
```

The suite covers exact balances, cross-customer denial, retrieval citations and abstention, the formless ₹5 lakh path, a wrong PIN, an idempotent second submit, the income-conflict review path, restart recovery, a ₹50 lakh rejection, and PDF text. Do not describe the 30-phrase and 13-question sets as field accuracy.

## 10. Docker

`docker-compose.yml` builds the API and an nginx image of the UI. It was not executed as part of the verified run. If Docker is available:

```bash
docker compose up --build
```

The UI is then http://127.0.0.1:8080 and the API remains http://127.0.0.1:8000. The container database is inside the API container, not `backend/data/`.

## 11. Optional local model

Leave this off for the interview demo. If Ollama is installed and `qwen2.5:3b` is pulled, start the API with:

```bash
BANK_LLM_PROVIDER=openai_compatible \
BANK_LLM_BASE_URL=http://127.0.0.1:11434/v1 \
BANK_LLM_MODEL=qwen2.5:3b \
BANK_LLM_API_KEY=ollama \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The model may only label an intent the deterministic parser missed, or paraphrase a page whose numbers already appear in the evidence. Balances, validation, EMI arithmetic, and submission stay in Python. This model was not scored on the checked-in sets in this workspace.

## 12. If it does not start

| What you see | What to do |
| --- | --- |
| `python` is 3.9 or `python3.12` is missing | Use the `uv` commands in section 3 |
| `npm` or `node` is not found | Install Node 20 or 22 and open a new terminal so `PATH` includes it |
| The UI loads and every call fails | The API is not on port 8000. Start terminal A and open http://127.0.0.1:8000/api/health |
| Port 8000 or 5173 is already in use | Stop the older process, or the demo is already running at http://127.0.0.1:5173 |
| Priya cannot start a loan | An open draft still exists. Send `cancel this application`, or reset `backend/data` while the API is stopped |
| The PDF pane is blank | The application card is the source of the filled fields. The file is also under `backend/data/pdfs/` after generation |
| A balance contains a rupee amount while accounts are disabled | That would be a defect. With `BANK_ACCOUNTS_ENABLED=false` the reply must not contain an amount |

## 13. What this submission does not claim

- The demo passwords and PIN are not a bank identity provider.
- SQLite is a single-writer file for the POC, not a ledger.
- Qwen2.5 3B is the provisional local candidate. It was not benchmarked here.
- Docker Compose is provided and was not run as part of the recorded test result.
- Home loans can be explained from the approved pages. They cannot be submitted.
