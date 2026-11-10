# Interview narrative

I would walk a hiring panel through this POC as a channel in front of controls the bank already needs, not as a chatbot that invents banking.

## Business problem

A personal loan at many banks is still three forms. The customer retypes a name, address, and employer the bank already verified at onboarding, hunts for the right document checklist, and only then discovers an amount that was never eligible. Drop-off happens in the forms. The operational risk is the opposite problem: a free-text assistant that "fills the form" by guessing income or skipping a signature.

The useful design is a conversation that collects only what is missing, writes a typed application the origination system already understands, and shows that document back before anything is submitted.

## Architecture

The browser is React and TypeScript. It posts each utterance to FastAPI and renders the reply, citations, the tool trace, and a read-only application card. There is no loan form in the client.

FastAPI authenticates the demo session and builds an orchestrator with that customer id. The orchestrator labels the turn. A balance question calls `BankingTools`. A product question calls the retriever. A loan question steps a LangGraph graph whose nodes are pure functions: merge the field we asked for, check consent, copy the profile, ask for the next gap, validate, or submit.

Side effects stay in the tool facade. The graph returns a new state dict. The facade then saves the draft, writes the PDF, or runs the conditional submit. That split is what lets me replace SQLite with Spring Boot later without redrawing the conversation.

A concrete balance turn for Priya Sharma: she has two accounts, so the first reply asks whether she means savings ending 4582 or current ending 9081. When she says savings, `get_account_balance` reads 12,500,000 paise and the reply is "₹1,25,000". The ledger balance of ₹1,30,000 is a different column and is not spoken as the available balance. The tool does not take a customer id argument. The session does.

A concrete loan turn: "I want to apply for a ₹5 lakh loan" stores 50,000,000 paise and asks for consent. "Yes" is the first time the profile is read. She is not asked to retype her Bengaluru address. The graph then asks employment, employer, income, tenure, and purpose. The salary slip is extracted with regular expressions. Validation is Python, not a prompt. The PDF has three sections matching `poc-loan-v1`. She confirms with PIN 2580 and receives a reference `HB-PL-…`.

## Technology choice

Python is the right orchestration runtime because LangGraph and the PDF and extraction libraries live there, and because the banking rules are easier to test as plain functions than as prompts. React with TypeScript keeps the channel small: chat, citations, upload, PDF preview. I would not put loan rules in the client.

LangChain is the retriever interface, so a neural embedding model can replace the hashed vectors without a new call shape. LangGraph is only the loan state machine. I did not build a swarm of agents. Balance and retrieval are single tool calls, which are easier to authorise and to test.

The default model setting is deterministic. On this machine, an Apple M4 Pro with 24 GB of memory and no Ollama install, I did not run a bake-off. The provisional candidate is Qwen2.5 3B Instruct behind an OpenAI-compatible local API, and only for two jobs: labelling an utterance the patterns miss, and paraphrasing a page whose numbers already pass a grounding check. I will not turn that flag on until those 30 intent phrases and 13 knowledge questions, plus the bank's own utterances, have been scored against it.

## Design principles

The policy figures live in one module and are quoted by the knowledge pages. Tests fail if the page drifts. Validation does not import FastAPI. The graph does not import SQLAlchemy. The tool list is closed. That is what keeps a future core-banking adapter inside `BankingTools` and `build_contract` instead of smeared through the prompts.

`poc-loan-v1` is explicitly a stand-in. The repository had no real three-form schema. Replacing it is a mapping function, not a new assistant.

## Usability

Priya never sees a form. She sees one question at a time, her own profile repeated back after consent, and a PDF she can read. The application card is not editable. If she asks for the document checklist in the middle of the application, the orchestrator answers from the approved page and then returns to the missing field. If she has two accounts and asks for "my balance", she is asked which one rather than being shown an arbitrary account.

## Accuracy

Balances are the tool payload, formatted from paise. If the account service is disabled, the reply has no rupee amount. Product answers cite `DOC-PL-DOCS` or the relevant page id. Coverage under 0.5 abstains. A question that matches both personal and home loan pages, and names neither, asks which product. A salary credit in the transaction list is not treated as income. The EMI example is computed from the fictional 12.5% rate only when that rate is in the retrieved text. The model is not allowed to introduce a 0% rate or any other number that is not in the evidence.

## Security

The demo sign-in is labelled as a demo. The token carries the subject. Account reads check ownership and return 403 for Arjun asking for Priya's account. Uploaded text and retrieved text are untrusted: injection lines are stripped, and they cannot change tools or the system instructions. The PIN is checked before the confirmation flag exists. Five failures lock confirmation. Audit rows record the tool name, not the password. The PDF download path is built from the loan id after an ownership check, not from a client-supplied filename.

I would tell the panel this is a trust-boundary demonstration. It is not a claim that the HMAC demo token is fit for a bank.

## Human oversight

The customer confirms the PDF. That is one gate. The second gate is a reviewer, and only when the evidence disagrees: income off by more than 10%, a name mismatch, low extraction confidence, or a missing employer. A conflicting slip that says ₹50,000 against declared ₹80,000 pauses at `pending_review`. The reviewer approves, requests information, or rejects. Approval puts the customer back at the PIN step. A clean file skips the reviewer and still cannot submit without the PIN. A second "I confirm" after success returns the same reference.

## Scalability

I would keep this process as the orchestration service. Accounts, KYC, documents, and origination stay on the bank's Java Spring Boot APIs. Drafts, checkpoints, and audit move to Postgres. PDFs move to object storage. The core ledger is never this database. Rate limits move out of process memory. The model, if enabled, stays inside the bank network. The graph and the React channel do not need to be rewritten for that move.

## Trade-offs

I use a deterministic tool when the answer is a balance, a fee from policy code, or a submit decision. I use retrieval when the answer is a procedure or a checklist that product owners edit as pages. I use the graph when the conversation has a draft, a missing-field order, and gates. I would add another agent only for a second product with its own contract, not to rephrase a balance.

What I would not claim in the room: production accuracy, a measured model comparison, or that SQLite is a ledger. What I can claim is the path that is implemented and tested: exact balances, cited documents, and a formless ₹5 lakh application that becomes a validated PDF and a reference only after confirmation.
