export type Citation = { doc_id: string; title: string; version: string };
export type ToolTrace = { name: string; ok: boolean; detail: string };
export type ApplicationView = {
  id: number;
  schema_version: string;
  status: string;
  reference: string | null;
  product_code: string | null;
  requested_amount: string | null;
  tenure_months: number | null;
  purpose: string | null;
  employment_type: string | null;
  employer_name: string | null;
  monthly_income: string | null;
  personal: Record<string, string>;
  provenance: Record<string, string>;
  missing_fields: string[];
  validation_errors: string[];
  review_reasons: string[];
  review_status: string | null;
  review_notes: string | null;
  expected_field: string | null;
  customer_confirmed: boolean;
  documents: { id: number; doc_type: string; filename: string; confidence: number | null }[];
};
export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  tool_trace?: ToolTrace[];
};
export type ChatResult = {
  conversation_id: string;
  reply: string;
  intent: string;
  citations: Citation[];
  tool_trace: ToolTrace[];
  application: ApplicationView | null;
  pdf_ready: boolean;
  actions: string[];
};
export type Session = {
  access_token: string;
  display_name: string;
  role: string;
  customer_ref: string;
};

async function request<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      /* ignore non-json errors */
    }
    throw new Error(detail);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/pdf")) return (await response.blob()) as T;
  return response.json();
}

export function login(email: string, password: string) {
  return request<Session>("/api/auth/login", null, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function me(token: string) {
  return request<{ display_name: string; role: string; customer_ref: string }>("/api/me", token);
}

export function sendChat(token: string, message: string, conversationId: string | null) {
  return request<ChatResult>("/api/chat", token, {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}

export function latestConversation(token: string) {
  return request<{ conversation_id: string | null; messages: ChatMessage[] }>("/api/conversations/latest", token);
}

export function currentLoan(token: string) {
  return request<{ application: ApplicationView | null }>("/api/loans/current", token);
}

export function uploadDocument(token: string, conversationId: string, file: File) {
  const body = new FormData();
  body.set("file", file);
  return request<ChatResult>(`/api/conversations/${conversationId}/documents`, token, { method: "POST", body });
}

export function confirmLoan(token: string, loanId: number, pin: string, conversationId: string | null) {
  return request<ChatResult>(`/api/loans/${loanId}/confirm`, token, {
    method: "POST",
    body: JSON.stringify({ pin, conversation_id: conversationId }),
  });
}

export function pendingReviews(token: string) {
  return request<{
    reviews: {
      id: number;
      customer_name: string;
      customer_ref: string;
      status: string;
      review_reasons: string[];
      requested_amount_paise: number | null;
      monthly_income_paise: number | null;
    }[];
  }>("/api/reviews/pending", token);
}

export function decideReview(token: string, loanId: number, decision: string, notes: string) {
  return request<{ application: ApplicationView }>(`/api/reviews/${loanId}`, token, {
    method: "POST",
    body: JSON.stringify({ decision, notes }),
  });
}

export async function loanPdf(token: string, loanId: number) {
  const blob = await request<Blob>(`/api/loans/${loanId}/document`, token);
  return blob;
}
