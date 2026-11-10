import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import {
  ApplicationView,
  ChatMessage,
  ChatResult,
  Session,
  confirmLoan,
  currentLoan,
  decideReview,
  latestConversation,
  loanPdf,
  login,
  me,
  pendingReviews,
  sendChat,
  uploadDocument,
} from "./api";

const TOKEN_KEY = "harbourline.token";
const SESSION_KEY = "harbourline.session";
const DEMOS = [
  {
    label: "Priya Sharma",
    email: "priya.sharma@example.com",
    password: "demo-pass-priya",
    pin: "2580",
    hint: "Savings ending 4582 and current ending 9081",
  },
  {
    label: "Arjun Mehta",
    email: "arjun.mehta@example.com",
    password: "demo-pass-arjun",
    pin: "1470",
    hint: "One savings account ending 2210",
  },
  {
    label: "Demo Reviewer",
    email: "reviewer@harbourline.example",
    password: "demo-pass-reviewer",
    pin: "",
    hint: "Reviews paused applications",
  },
];

export function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = sessionStorage.getItem(TOKEN_KEY);
    const saved = sessionStorage.getItem(SESSION_KEY);
    if (!token || !saved) {
      setReady(true);
      return;
    }
    me(token)
      .then((profile) => setSession({ ...JSON.parse(saved), ...profile, access_token: token }))
      .catch(() => {
        sessionStorage.clear();
      })
      .finally(() => setReady(true));
  }, []);

  function signIn(next: Session) {
    sessionStorage.setItem(TOKEN_KEY, next.access_token);
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
    setSession(next);
  }

  function signOut() {
    sessionStorage.clear();
    setSession(null);
  }

  if (!ready) return <p className="boot">Opening Harbourline…</p>;
  if (!session) return <Login onSuccess={signIn} />;
  return (
    <Shell session={session} onSignOut={signOut}>
      {session.role === "reviewer" ? <Reviewer token={session.access_token} /> : <CustomerDesk session={session} />}
    </Shell>
  );
}

function Shell({
  session,
  onSignOut,
  children,
}: {
  session: Session;
  onSignOut: () => void;
  children: ReactNode;
}) {
  return (
    <>
      <a className="skip" href="#main">
        Skip to conversation
      </a>
      <header className="top">
        <div>
          <p className="brand">Harbourline</p>
          <p className="tag">Fictional assistant POC. Not a real bank.</p>
        </div>
        <div className="who">
          <span>
            {session.display_name}
            <small>{session.customer_ref}</small>
          </span>
          <button type="button" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </header>
      <main id="main">{children}</main>
    </>
  );
}

function Login({ onSuccess }: { onSuccess: (session: Session) => void }) {
  const [email, setEmail] = useState(DEMOS[0].email);
  const [password, setPassword] = useState(DEMOS[0].password);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSuccess(await login(email, password));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login" id="main">
      <section>
        <p className="brand">Harbourline</p>
        <h1>Talk to the bank. Don't fill in the loan form.</h1>
        <p>
          This local POC uses fictional customers. Balances come from SQLite. Loan answers come from approved sample
          pages. Nothing here is a real offer.
        </p>
        <form onSubmit={submit}>
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
      <aside>
        <h2>Demo customers</h2>
        {DEMOS.map((demo) => (
          <button
            key={demo.email}
            type="button"
            className="demo"
            onClick={() => {
              setEmail(demo.email);
              setPassword(demo.password);
            }}
          >
            <strong>{demo.label}</strong>
            <span>{demo.hint}</span>
            <span>
              {demo.email}
              {demo.pin ? ` · PIN ${demo.pin}` : ""}
            </span>
          </button>
        ))}
      </aside>
    </main>
  );
}

function CustomerDesk({ session }: { session: Session }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [application, setApplication] = useState<ApplicationView | null>(null);
  const [pdfReady, setPdfReady] = useState(false);
  const [actions, setActions] = useState<string[]>([]);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pin, setPin] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    latestConversation(session.access_token)
      .then((payload) => {
        setConversationId(payload.conversation_id);
        setMessages(payload.messages || []);
      })
      .catch(() => undefined);
    currentLoan(session.access_token)
      .then((payload) => {
        setApplication(payload.application);
        setPdfReady(Boolean(payload.application && ["awaiting_confirmation", "submitted", "pending_review"].includes(payload.application.status)));
      })
      .catch(() => undefined);
  }, [session.access_token]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [messages, busy]);

  useEffect(() => {
    if (!pdfReady || !application) {
      setPdfUrl(null);
      return;
    }
    let cancelled = false;
    let url: string | null = null;
    loanPdf(session.access_token, application.id)
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setPdfUrl(url);
      })
      .catch(() => {
        if (!cancelled) setPdfUrl(null);
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [pdfReady, application?.id, application?.status, session.access_token]);

  function absorb(result: ChatResult, userText?: string) {
    setConversationId(result.conversation_id);
    setMessages((current) => [
      ...current,
      ...(userText ? [{ role: "user" as const, content: userText }] : []),
      {
        role: "assistant" as const,
        content: result.reply,
        citations: result.citations,
        tool_trace: result.tool_trace,
      },
    ]);
    setApplication(result.application);
    setPdfReady(result.pdf_ready);
    setActions(result.actions);
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setBusy(true);
    setError("");
    try {
      absorb(await sendChat(session.access_token, text, conversationId), text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The assistant could not answer.");
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(file: File) {
    if (!conversationId) {
      setError("Start the loan conversation before uploading a document.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      absorb(await uploadDocument(session.access_token, conversationId, file), `Uploaded ${file.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm(event: FormEvent) {
    event.preventDefault();
    if (!application) return;
    setBusy(true);
    setError("");
    try {
      absorb(await confirmLoan(session.access_token, application.id, pin, conversationId));
      setPin("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirmation failed.");
    } finally {
      setBusy(false);
    }
  }

  const pinHint = session.customer_ref === "CUS-1001" ? "2580" : session.customer_ref === "CUS-1002" ? "1470" : "";

  return (
    <div className="desk">
      <section className="chat" aria-label="Conversation">
        <div className="log" ref={scroller} aria-live="polite">
          {messages.length === 0 && (
            <p className="empty">
              Ask for a balance, a loan policy, or say you want a personal loan. You will not be given a form to fill
              in.
            </p>
          )}
          {messages.map((message, index) => (
            <article key={index} className={message.role}>
              <p>{message.content}</p>
              {message.citations && message.citations.length > 0 && (
                <ul className="cites">
                  {message.citations.map((citation) => (
                    <li key={citation.doc_id}>
                      {citation.doc_id} · {citation.title} · v{citation.version}
                    </li>
                  ))}
                </ul>
              )}
              {message.tool_trace && message.tool_trace.length > 0 && (
                <p className="tools">Checked with {message.tool_trace.map((item) => item.name).join(", ")}</p>
              )}
            </article>
          ))}
          {busy && <p className="pending">Working with the banking services…</p>}
        </div>
        {error && <p className="error">{error}</p>}
        <form className="composer" onSubmit={onSend}>
          <label className="sr" htmlFor="message">
            Message
          </label>
          <textarea
            id="message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Ask about a balance, a policy, or a personal loan"
            rows={2}
          />
          <div className="composer-actions">
            <input
              ref={fileRef}
              type="file"
              accept=".txt,.md,.pdf,text/plain,application/pdf"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onUpload(file);
                event.target.value = "";
              }}
            />
            <button type="button" onClick={() => fileRef.current?.click()} disabled={busy}>
              Upload document
            </button>
            <button type="submit" disabled={busy || !draft.trim()}>
              Send
            </button>
          </div>
        </form>
      </section>
      <aside className="panel">
        <h2>Application draft</h2>
        {!application && <p>No loan draft yet. The conversation will build one when you ask.</p>}
        {application && (
          <>
            <p className={`status status-${application.status}`}>{labelStatus(application.status)}</p>
            {application.reference && <p>Reference {application.reference}</p>}
            <dl>
              <dt>Schema</dt>
              <dd>{application.schema_version}</dd>
              <dt>Amount</dt>
              <dd>{application.requested_amount || "Still needed"}</dd>
              <dt>Tenure</dt>
              <dd>{application.tenure_months ? `${application.tenure_months} months` : "Still needed"}</dd>
              <dt>Purpose</dt>
              <dd>{application.purpose || "Still needed"}</dd>
              <dt>Employment</dt>
              <dd>{application.employment_type || "Still needed"}</dd>
              <dt>Employer</dt>
              <dd>{application.employer_name || "Still needed"}</dd>
              <dt>Monthly income</dt>
              <dd>{application.monthly_income || "Still needed"}</dd>
              <dt>Name</dt>
              <dd>
                {application.personal.first_name
                  ? `${application.personal.first_name} ${application.personal.last_name}`
                  : "Waiting for consent"}
              </dd>
            </dl>
            {application.missing_fields.length > 0 && application.status !== "submitted" && (
              <p>Still needed: {application.missing_fields.join(", ")}.</p>
            )}
            {application.review_reasons.length > 0 && (
              <div className="flag">
                <strong>Reviewer check</strong>
                <ul>
                  {application.review_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
                {application.review_notes && <p>{application.review_notes}</p>}
              </div>
            )}
            {actions.includes("confirm") && (
              <form onSubmit={onConfirm} className="confirm">
                <p>Review the document, then confirm. This is not a form. Nothing is submitted until the PIN matches.</p>
                <label>
                  Transaction PIN
                  <input
                    value={pin}
                    onChange={(event) => setPin(event.target.value)}
                    inputMode="numeric"
                    autoComplete="off"
                    maxLength={4}
                  />
                </label>
                {pinHint && <p className="hint">Fictional demo PIN for this customer: {pinHint}</p>}
                <button type="submit" disabled={busy || pin.length < 4}>
                  Confirm and submit
                </button>
              </form>
            )}
            {pdfUrl && (
              <iframe title="Completed loan application" src={pdfUrl} className="preview" />
            )}
          </>
        )}
      </aside>
    </div>
  );
}

function Reviewer({ token }: { token: string }) {
  const [items, setItems] = useState<Awaited<ReturnType<typeof pendingReviews>>["reviews"]>([]);
  const [notes, setNotes] = useState("Income difference accepted for this fictional POC.");
  const [error, setError] = useState("");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  async function refresh() {
    setItems((await pendingReviews(token)).reviews);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [token]);

  async function decide(id: number, decision: string) {
    setError("");
    try {
      await decideReview(token, id, decision, notes);
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
      setPdfUrl(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    }
  }

  async function openPdf(id: number) {
    const blob = await loanPdf(token, id);
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    setPdfUrl(URL.createObjectURL(blob));
  }

  return (
    <section className="reviewer">
      <h1>Review queue</h1>
      <p>Only applications the assistant paused are listed. Routine balance questions are not waiting here.</p>
      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p>No applications are paused.</p>}
      {items.map((item) => (
        <article key={item.id} className="review-card">
          <h2>
            {item.customer_name} · {item.customer_ref}
          </h2>
          <ul>
            {item.review_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <label>
            Note to the customer
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={2} />
          </label>
          <div className="composer-actions">
            <button type="button" onClick={() => openPdf(item.id)}>
              Open draft
            </button>
            <button type="button" onClick={() => decide(item.id, "approve")}>
              Approve
            </button>
            <button type="button" onClick={() => decide(item.id, "request_info")}>
              Request information
            </button>
            <button type="button" onClick={() => decide(item.id, "reject")}>
              Reject
            </button>
          </div>
        </article>
      ))}
      {pdfUrl && <iframe title="Application under review" src={pdfUrl} className="preview" />}
    </section>
  );
}

function labelStatus(status: string) {
  const labels: Record<string, string> = {
    collecting: "Collecting missing details",
    awaiting_document: "Waiting for a document",
    pending_review: "Paused for a reviewer",
    awaiting_confirmation: "Ready for your confirmation",
    submitted: "Submitted",
    rejected: "Rejected",
    declined: "Cancelled",
  };
  return labels[status] || status;
}
