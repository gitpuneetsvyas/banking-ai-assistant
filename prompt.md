# MASTER PROMPT — End-to-End Agentic AI Banking Assistant POC

## Senior Solution Architect | Python | React | TypeScript | LangChain | LangGraph | RAG

### 1. Your Role

Act as a **Senior Solution Architect, Agentic AI Architect and hands-on Full-Stack Engineer** responsible for designing, implementing, testing and demonstrating an end-to-end Agentic AI Banking Assistant.

Think like an experienced enterprise architect who must justify every technical decision to an interviewer.

Your expertise must cover:

- Python, FastAPI, Pydantic, SQLAlchemy
- React.js, TypeScript and modern frontend architecture
- LangChain, LangGraph, RAG, LLM tool calling and structured outputs
- SQLite for local banking POC data
- SOLID principles, clean architecture and domain-driven design
- Banking APIs, security, authorisation and transaction processing
- AI accuracy, human-in-the-loop, observability and evaluation
- Scalable architecture and production migration planning

**Your objective is to deliver a working POC, not just an architectural proposal.**

Do not assume unknown information, fabricate project results or claim functionality has been implemented unless it has actually been built and tested.

---

# 2. Core Business Problem

We have an existing banking web application offering three capabilities:

1. Bank account balance and account-detail enquiries.
2. Banking information retrieval, including loan products, policies and required documents.
3. A traditional loan application journey currently implemented as a guided tour across three forms.

We want to modernise the user experience using Agentic AI.

### Critical Functional Requirement

**The customer must never be required to manually fill out a loan application form.**

Instead:

- The customer interacts with an AI assistant through natural-language conversation.
- The assistant automatically retrieves available verified information.
- The assistant asks conversational questions only for missing information.
- The assistant collects supporting documents when required.
- The agentic layer maintains the complete application state internally.
- The system generates the final structured loan application using the existing three-form data contract.
- The customer reviews the completed application document and confirms submission.
- The existing banking backend remains responsible for validation, authorisation and final submission.

**The customer sees a conversation. The bank receives a completed, validated loan application form.**

The existing guided tour and three-form workflow should be retained at the backend contract/business-process level where appropriate, but not exposed as manual form-entry screens.

---

# 3. Functional Requirements

## FR-01: Account Balance Enquiry

### Customer interaction

Customer asks:

"What is my savings account balance?"

The assistant should:

1. Identify the authenticated customer.
2. Identify the requested bank account.
3. Ask a clarification question if multiple matching accounts exist.
4. Invoke an authorised balance enquiry tool.
5. Retrieve exact account information through a backend service.
6. Return the available or ledger balance with clear labelling and currency.
7. Mask sensitive account details.
8. Handle unavailable services gracefully.

### Example conversation

Customer: "What is my balance?"

AI: "You have two accounts: Savings ending 4582 and Current ending 9081. Which would you like to check?"

Customer: "Savings."

AI: "Your available savings account balance is ₹1,25,000, according to the latest account-service response."

These values are fictional demonstration data.

### Mandatory accuracy requirement

Account balances must come directly from the banking system of record or its authorised POC equivalent.

The LLM must never invent, estimate or calculate an authoritative balance.

For this use case, prefer deterministic Java/Python service logic and controlled tool calling rather than a complex multi-agent workflow.

---

## FR-02: Banking Information Retrieval Using RAG

### Customer interaction

Customer asks:

"What documents are required for a personal loan?"

Other examples:

- "What is the difference between a personal loan and a home loan?"
- "What is the eligibility requirement?"
- "Can I prepay my loan?"
- "What fees apply to this product?"

### Required behaviour

1. Understand the user's question.
2. Identify the relevant banking product or policy.
3. Retrieve approved information using RAG.
4. Use only authorised banking documents and knowledge sources.
5. Generate an answer supported by retrieved evidence.
6. Show source-document citations.
7. Ask clarifying questions when necessary.
8. Abstain when the information is unavailable or contradictory.
9. Never invent rates, fees, policies or eligibility rules.

### Architecture

Implement a RAG pipeline:

Document ingestion → parsing → chunking → embeddings → vector index → retrieval → evidence filtering → grounded answer.

Evaluate whether hybrid keyword and vector retrieval improves accuracy for banking policy documents.

Maintain source identifiers, document versions and access-control metadata.

The system must distinguish general banking information from customer-specific account or loan information.

---

## FR-03: AI-Guided Loan Application Without Forms

This is the **primary architectural demonstration**.

### Current system

The banking application currently has a guided journey involving three forms:

**Form 1 — Personal and KYC information**

Examples: first name, last name, address, date of birth and contact details.

**Form 2 — Employment, financial and loan information**

Examples: employment type, income, requested loan amount, tenure, purpose and supporting documents.

**Form 3 — Review, validation and submission**

The customer reviews the complete application, confirms declarations and submits the application.

These are proposed logical sections for the POC. Verify and preserve the actual field names and requirements if the existing three-form contracts are provided.

### Target system

**Remove the need for manual form interaction.**

Replace it with a conversation-driven loan application journey.

### Example customer conversation

Customer: "I want to apply for a personal loan of ₹5 lakh."

AI: "I can help you prepare the application. With your permission, I'll use the verified information already available in your banking profile."

Customer: "Yes."

AI: "I have retrieved your name and registered address. What is your current employment type?"

Customer: "Salaried."

AI: "What is your monthly income?"

Customer: "₹80,000."

AI: "Thank you. I need to verify your income using the required supporting documents. You can upload a salary slip securely."

Customer uploads a document.

AI: "I have extracted the relevant information and checked it against the required fields. I'll now prepare your application for review."

The system generates a completed loan application document.

AI: "Your personal loan application draft is ready. Please review the completed document and confirm whether you want to submit it."

The customer reviews the document and explicitly confirms.

The application is submitted through the authorised backend service only after all mandatory validation and confirmation steps succeed.

### Required AI capabilities

- Natural-language intent understanding
- Context-aware multi-turn conversation
- Customer profile retrieval
- Missing-information detection
- Conversational slot filling
- Document upload and extraction
- Data provenance tracking
- Field-level verification
- Business-rule validation
- Controlled workflow transitions
- Application document generation
- Human review
- Explicit confirmation
- Secure application submission
- Session recovery

### Critical design principle

The AI should **not generate an arbitrary loan form based on free-text conversation**.

Instead, it must populate a typed, validated application object matching the bank's existing loan application schema.

A deterministic document generation service should then use that validated object to generate the final PDF or read-only document.

The final form may be displayed for customer review, but it must not require the customer to manually complete fields.

---

# 4. High-Level Architecture

Design and implement the following logical architecture.

```text
               BANK CUSTOMER
                     |
                     v
      +-----------------------------+
      | REACT + TYPESCRIPT WEB APP  |
      |-----------------------------|
      | Conversational AI Assistant |
      | Account Enquiries           |
      | Banking Information         |
      | Loan Application Chat       |
      | Document Upload             |
      | Completed Loan PDF Preview  |
      +--------------+--------------+
                     |
                     v
      +-----------------------------+
      | FASTAPI BACKEND             |
      |-----------------------------|
      | Authentication              |
      | Authorisation               |
      | Customer Context            |
      | Consent / Audit             |
      | Session Management          |
      +--------------+--------------+
                     |
                     v
      +-----------------------------+
      | AI INTENT ROUTER            |
      |-----------------------------|
      | Balance Enquiry             |
      | Knowledge Retrieval         |
      | Loan Application            |
      +--------------+--------------+
                     |
          +----------+-----------+
          |          |           |
          v          v           v
     BALANCE      RAG INFO     LOAN AGENT
      TOOL        TOOL        LANGGRAPH
          |          |           |
          |          |      +----+------+
          |          |      | Profile   |
          |          |      | KYC       |
          |          |      | Documents |
          |          |      | Validate  |
          |          |      | Review    |
          |          |      +----+------+
          |          |           |
          +----------+-----------+
                     |
                     v
      +-----------------------------+
      | CONTROLLED BANKING SERVICES |
      |-----------------------------|
      | Customer Profile            |
      | Account Balance             |
      | Transactions                |
      | Loan Draft                  |
      | Business Validation         |
      | Loan Submission             |
      +--------------+--------------+
                     |
                     v
      +-----------------------------+
      | SQLITE DATABASE            |
      |-----------------------------|
      | Customers                   |
      | Accounts                    |
      | Transactions                |
      | Loan Applications           |
      | Consent / Audit             |
      +-----------------------------+
```

Use a modular-monolith architecture for the POC unless there is a strong reason to distribute services.

Explain how the same architecture can later support existing Java Spring Boot banking APIs without rewriting the AI orchestration layer.

---

# 5. Agentic Workflow and Tool Chain

Use **LangGraph for the stateful loan application process**.

Suggested workflow:

```text
Customer requests loan
         |
         v
Intent / Workflow Router
         |
         v
Consent Check
         |
         v
Retrieve Customer Profile
         |
         v
Load Existing Loan Draft
         |
         v
Identify Missing Information
         |
     +---+---+
     |       |
   Missing  Complete
     |       |
     v       v
Ask User  Validate Data
     |       |
     v       v
Update    Verify Evidence
State        |
     |       v
     +----> Generate PDF Draft
                 |
                 v
          Human Review
                 |
                 v
        Customer Confirmation
                 |
                 v
        Final Backend Validation
                 |
                 v
        Submit Loan Application
                 |
                 v
        Application Reference
```

### Tool Chain Design

Create controlled tools such as:

- `list_customer_accounts`
- `get_account_balance`
- `get_recent_transactions`
- `search_bank_knowledge`
- `get_customer_profile`
- `get_customer_kyc`
- `get_loan_requirements`
- `extract_document_fields`
- `get_loan_draft`
- `update_loan_draft`
- `validate_loan_application`
- `generate_loan_document`
- `request_human_review`
- `submit_loan_application`

Each tool must have a typed input/output contract, authorisation checks, audit metadata, error handling and defined execution limits.

**Never grant the LLM unrestricted database access.**

For example, `get_account_balance` must derive the customer identity from the authenticated server context rather than trusting arbitrary account ownership details supplied by the LLM.

The final submission tool must only operate on a validated, authorised and explicitly confirmed application.

---

# 6. LangGraph State Management

Define structured application state containing:

- Authenticated customer reference
- Conversation ID
- Loan application ID
- Loan product
- Requested amount
- Personal details
- Employment information
- Financial information
- Document references
- Field provenance
- Verification status
- Missing required fields
- Validation errors
- Customer consent
- Human-review status
- Submission authorisation
- Workflow status

Use Pydantic schemas and clear state transitions.

Persist checkpoints so the customer can resume the conversation.

Enforce maximum execution steps and prevent infinite agent loops.

Ensure that repeated requests cannot create duplicate applications or duplicate loan submissions.

---

# 7. Lightweight LLM Selection

Choose a **small, efficient model** suitable for the POC, rather than automatically selecting an expensive flagship LLM.

Evaluate realistically available candidates from lightweight model families such as Qwen, Phi or Gemma.

Before final selection, establish:

- Available hardware
- Memory and CPU/GPU capacity
- Internet availability
- Local or hosted inference preference
- Model licences
- Expected request volume
- Privacy requirements
- Required tool-calling reliability

Evaluate candidate models for:

- Intent classification
- Tool-call accuracy
- Structured JSON generation
- Multi-turn conversation
- Grounded RAG responses
- Latency
- Memory footprint
- Operational cost

Do not assume model capability from its name or parameter count.

Select the smallest model that satisfies measured acceptance criteria.

If benchmarking is unavailable, label the model choice provisional and explain how it will be validated.

Use deterministic application code for balances, financial calculations and final business decisions.

---

# 8. SOLID and Clean Architecture

Apply SOLID principles pragmatically.

**Single Responsibility:** Keep conversation orchestration, account retrieval, knowledge search, validation, document generation and loan persistence separate.

**Open/Closed:** Allow new banking tools, loan products and model providers through clearly defined extensions.

**Liskov Substitution:** Support interchangeable repository, model and retrieval implementations.

**Interface Segregation:** Use focused contracts such as AccountReader, KnowledgeRetriever, LoanValidator and LoanDocumentGenerator.

**Dependency Inversion:** Domain workflows must not depend directly on SQLite, a particular LLM or a vector database.

Use clear module boundaries and dependency injection.

Do not introduce excessive abstraction merely to demonstrate design patterns.

---

# 9. Usability, Accuracy and Security

These are the three most important non-functional requirements.

## Usability

The customer should be able to complete the banking journey without learning the underlying application structure.

Provide:

- A single conversational interface
- Natural-language questions
- Context retention
- Smart clarification
- Minimal repetition
- Transparent processing status
- Document upload
- Conversation recovery
- Completed loan document preview
- Clear consent and confirmation interactions
- Accessibility and responsive design

The AI must ask only for information that is missing, expired, inconsistent or requires explicit customer verification.

## Accuracy

Financial data must be grounded in trusted systems.

Implement:

- Authoritative balance retrieval
- RAG citations
- Field provenance
- Schema validation
- Deterministic business-rule validation
- Explicit handling of missing values
- Cross-checking extracted documents
- Conflict detection
- Abstention for unsupported responses
- Human escalation when required

The assistant must not invent income, employment, credit eligibility, loan terms or policy information.

## Security

Implement:

- Secure authentication or clearly labelled mock authentication
- Per-customer authorisation
- Least-privilege tool execution
- Protection against cross-account data access
- Consent tracking
- PII masking
- Secure document storage
- Audit events
- Prompt-injection protection
- Output validation
- Rate limiting
- Safe error handling
- Explicit confirmation before loan submission

No LLM-generated tool argument should override the authenticated customer context.

Do not claim real banking-grade compliance based solely on POC controls.

---

# 10. Human-in-the-Loop Architecture

Human oversight must operate at two levels.

### Customer-in-the-Loop

Before submission:

1. Generate the completed loan application.
2. Display a read-only review document.
3. Clearly identify unverified or conflicting details.
4. Require explicit customer confirmation.
5. Perform any required step-up authentication.
6. Revalidate the application.
7. Submit only after all conditions are satisfied.

### Bank Reviewer-in-the-Loop

Escalate the application to an authorised bank reviewer when:

- KYC records conflict
- Document extraction is uncertain
- Required evidence is missing
- A policy exception is detected
- The workflow encounters a high-risk condition

The reviewer can approve, reject or request further information.

LangGraph must support safe workflow pause and resume.

### Continuous Quality Evaluation

Build a small evaluation workflow for:

- Reviewing sampled AI conversations
- Rating accuracy and usefulness
- Detecting hallucinations
- Inspecting failed tool calls
- Monitoring unsupported answers
- Reviewing retrieval quality
- Testing prompt and model changes
- Recording human feedback

Use privacy-preserving review data and authorised access.

Do not require a human to approve every routine balance enquiry; use proportionate controls based on risk.

---

# 11. Banking Data Model

Design an SQLite schema suitable for the POC.

Include:

- Customers
- Accounts
- Transactions
- Customer KYC
- Loan Products
- Loan Applications
- Loan Application Fields
- Uploaded Document Metadata
- Consent Records
- Agent Workflow Checkpoints
- Human Review Decisions
- Audit Events

Use fictional records.

Ensure relational integrity, constraints and appropriate indexes.

Clearly explain SQLite's concurrency and availability limitations and the proposed production migration path.

Do not treat SQLite as a production core banking ledger.

---

# 12. RAG Architecture and Knowledge Base

Create a small, fictional but internally consistent banking knowledge base.

Include approved sample documents about:

- Personal loan eligibility
- Required documents
- Loan application process
- Repayment and EMI information
- Prepayment rules
- General account information

Label all policies, rates and fees as fictional POC examples.

Implement:

1. Document ingestion
2. Parsing
3. Chunking
4. Embeddings
5. Vector indexing
6. Retrieval
7. Evidence selection
8. Answer generation
9. Citation verification
10. Evaluation

Use a lightweight embedding model and local retrieval engine where practical.

Ensure that document content cannot inject instructions into the agent's system or tool policies.

---

# 13. Testing and Quality Gates

Implement automated tests for all three journeys.

### Balance Enquiry

Verify:

- Correct balance retrieval
- Multiple-account clarification
- Account masking
- Cross-customer access denial
- Backend failure handling
- No fabricated values

### RAG Information Retrieval

Verify:

- Relevant document retrieval
- Valid citations
- Correct handling of missing evidence
- No invented rates or policies
- Prompt-injection resistance

### Loan Application

Verify:

- Verified profile auto-population
- Missing-information questions
- Document extraction handling
- Complete structured application state
- Business-rule validation
- Final document generation
- Required human review
- Explicit customer confirmation
- Submission authorisation
- Idempotent submission
- Workflow recovery

### Provisional POC Quality Targets

Define and evaluate:

- 100% exact-match balance correctness for the controlled test dataset
- Zero successful cross-customer access attempts
- Zero submissions without explicit confirmation
- 100% schema-valid submitted applications
- At least 95% intent-classification accuracy on a representative evaluation set
- At least 95% evidence-supported RAG factual claims on a representative evaluation set

These are proposed targets, not achieved metrics.

Provide actual results only after executing the tests.

---

# 14. POC Versus Production Architecture

Keep the POC focused and economical.

### POC Technology Choices

- React + TypeScript
- Python FastAPI
- LangChain
- LangGraph
- SQLite
- Local RAG knowledge base
- Lightweight LLM
- Deterministic banking tools
- PDF generation
- Human-review workflow

### Production Evolution

Explain how the design can migrate to:

- Enterprise banking APIs
- Java Spring Boot microservices
- PostgreSQL or existing transactional databases
- Managed identity and MFA
- Distributed workflow persistence
- Enterprise secrets management
- Managed container deployment
- Horizontal scaling
- Centralised monitoring
- Enterprise search infrastructure
- Durable asynchronous workflows
- High availability and disaster recovery

Show the trade-offs between a simple POC and production requirements.

Do not introduce unnecessary infrastructure in the initial implementation.

---

# 15. Expected Architecture Deliverables

Produce:

1. Business requirement analysis
2. Functional and non-functional requirements
3. Assumptions and open questions
4. Existing versus proposed customer journey
5. High-level architecture diagram
6. Mobile-friendly dotted architecture diagram
7. LangGraph workflow diagram
8. Tool-chain architecture
9. Sequence diagram for balance enquiry
10. Sequence diagram for RAG information retrieval
11. Sequence diagram for conversational loan application
12. Data model and ER diagram
13. API and tool contracts
14. Security and trust-boundary architecture
15. Human-in-the-loop workflow
16. Lightweight LLM selection ADR
17. SOLID design explanation
18. Error-handling and recovery strategy
19. Testing and evaluation strategy
20. Production migration roadmap

Use Mermaid and ASCII diagrams with clear descriptions.

---

# 16. Required Working Implementation

Implement a complete local application.

Deliver:

- React + TypeScript conversational frontend
- FastAPI application
- SQLite schema and fictional seed data
- Authentication and authorisation demonstration
- Account enquiry tools
- LangChain RAG implementation
- LangGraph loan workflow
- Structured application state
- Document upload and extraction handling
- Loan validation engine
- Completed loan application PDF generator
- Customer confirmation workflow
- Human-review functionality
- Loan submission simulation
- Audit logging
- Automated tests
- Docker Compose where useful
- Environment configuration
- Complete README
- Architecture documentation

Provide exact commands to install, run and test the solution.

Do not claim successful execution without verifying it.

---

# 17. Interview Demonstration

Prepare a 10-minute Senior Solution Architect demonstration.

### Demo 1 — Balance

Customer: "What is my savings balance?"

Show the AI identifying the intent, invoking the authorised tool and returning the exact SQLite value.

### Demo 2 — Banking Information

Customer: "What documents are required for a personal loan?"

Show RAG retrieval, approved document citations and a grounded answer.

### Demo 3 — Formless Loan Journey

Customer: "I want a personal loan of ₹5 lakh."

Show:

- Conversational information collection
- Verified profile retrieval
- Contextual questions
- Agent workflow state
- Document processing
- Data validation
- Completed loan application generation
- Read-only PDF preview
- Customer confirmation
- Human escalation if required
- Final submission
- Application reference

### Demo 4 — Security

Attempt to retrieve another customer's balance and demonstrate backend authorisation denial.

### Demo 5 — Accuracy

Ask about an unsupported policy and demonstrate safe abstention.

### Demo 6 — Human-in-the-Loop

Introduce conflicting customer information and demonstrate workflow pause, reviewer decision and controlled resumption.

---

# 18. Final Interview Narrative

Prepare a first-person explanation addressing:

**Business problem:** Why traditional form-based banking journeys create friction.

**Architecture:** How the conversational frontend, FastAPI, LangGraph, tools, RAG and banking services interact.

**Technology choice:** Why Python, React, TypeScript, LangChain, LangGraph and a lightweight LLM were selected.

**Design principles:** How SOLID and clean architecture preserve maintainability.

**Usability:** Why customers no longer need to navigate three forms.

**Accuracy:** How all financial information remains grounded and validated.

**Security:** How authentication, authorisation, permissions and consent are enforced.

**Human oversight:** How customer confirmation, bank review and ongoing evaluation are integrated.

**Scalability:** How the POC can evolve into production.

**Trade-offs:** When deterministic APIs, RAG or multi-agent orchestration should be used.

The final explanation must be suitable for a Senior Solution Architect interview and include practical request/response flows rather than generic AI terminology.

---

# 19. Execution Instructions

Work in the following order:

**Phase 1 — Requirement validation**

Review the requirements and available project files. Identify missing details and ask only essential clarifying questions. If the actual three-form schemas are unavailable, define clearly labelled POC contracts that can be replaced later.

**Phase 2 — Architecture**

Produce the proposed design, diagrams, data contracts, trust boundaries and technology-selection reasoning.

**Phase 3 — Implementation**

Build the banking backend and deterministic tools first. Then implement RAG, LangGraph, conversational UI, loan document generation and human review.

**Phase 4 — Testing**

Execute unit, integration, security and end-to-end tests. Report actual findings and failures.

**Phase 5 — Demonstration**

Provide a working demo, exact startup steps and the architecture interview walkthrough.

**Phase 6 — Production readiness**

Document limitations, unresolved risks, cost, scalability and security improvements required for production.

### Mandatory Rules

- Never invent bank balances, customer data or banking policies.
- Never allow arbitrary LLM-generated SQL.
- Never expose another customer's financial information.
- Never use unverified LLM values as authoritative financial data.
- Never submit an application without explicit customer confirmation.
- Never bypass deterministic business validation.
- Never silently assume missing customer information.
- Never fabricate performance metrics or successful test results.
- Never add unnecessary infrastructure for an interview POC.
- Never expose manual loan forms to the customer during information collection.

## Final Success Criteria

The application is successful when a customer can:

1. **Ask:** "What is my bank balance?" and receive the exact authorised account balance.
2. **Ask:** "What documents are needed for a personal loan?" and receive a grounded, cited answer.
3. **Say:** "I want to apply for a ₹5 lakh loan," complete the entire application through conversation, and receive a **fully populated, structured loan application document ready for review and secure submission**, without manually filling out any forms.

The solution must demonstrate **usability, accuracy, security, SOLID design, appropriate agentic tool orchestration, a justified lightweight LLM, human-in-the-loop evaluation and a credible path from POC to production**.
