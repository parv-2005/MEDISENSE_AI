/** Typed client for the MediSense AI FastAPI backend. */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "medisense.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData) && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, `Could not reach the server at ${API_URL}. Is the backend running?`);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? formatDetail((data as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  return data as T;
}

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
      .join("; ");
  }
  return JSON.stringify(detail);
}

// ------------------------------------------------------------------ types
export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export type ReportStatus = "uploaded" | "extracting" | "extracted" | "analyzing" | "analyzed" | "failed";

export interface Report {
  id: string;
  user_id: string;
  original_filename: string;
  stored_filename: string;
  content_type: string;
  size_bytes: number;
  status: ReportStatus;
  extraction_method: "digital" | "ocr" | null;
  page_count: number | null;
  extracted_text: string | null;
  has_analysis: boolean;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export type FindingStatus = "low" | "normal" | "high" | "abnormal" | "unknown";

export interface Finding {
  parameter: string;
  value: string;
  reference_range: string;
  status: FindingStatus;
  explanation: string;
}

export interface ReportAnalysis {
  report_type: string;
  summary: string;
  findings: Finding[];
  abnormal_flags: string[];
  insights: string[];
  recommendations: string[];
  urgency: "routine" | "soon" | "urgent" | "unknown";
  disclaimer: string;
}

export interface Analysis {
  id: string;
  report_id: string;
  user_id: string;
  model: string;
  analysis: ReportAnalysis;
  created_at: string;
}

export interface SourceChunk {
  chunk_index: number;
  text: string;
  score: number | null;
}

export interface Answer {
  id: string;
  report_id: string;
  question: string;
  answer: string;
  sources: SourceChunk[];
  model: string;
  created_at: string;
}

// ------------------------------------------------------------------ endpoints
export const api = {
  register: (body: { name: string; email: string; password: string }) =>
    request<TokenResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => request<User>("/api/auth/me"),

  listReports: () => request<Report[]>("/api/reports"),
  getReport: (id: string) => request<Report>(`/api/reports/${id}`),
  uploadReport: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Report>("/api/reports/upload", { method: "POST", body: form });
  },
  deleteReport: (id: string) => request<void>(`/api/reports/${id}`, { method: "DELETE" }),

  extract: (id: string) => request<Report>(`/api/reports/${id}/extract`, { method: "POST" }),
  analyze: (id: string) => request<Analysis>(`/api/reports/${id}/analyze`, { method: "POST" }),
  getAnalysis: (id: string) => request<Analysis>(`/api/reports/${id}/analysis`),

  ask: (id: string, question: string) =>
    request<Answer>(`/api/reports/${id}/ask`, { method: "POST", body: JSON.stringify({ question }) }),
  qaHistory: (id: string) => request<Answer[]>(`/api/reports/${id}/qa`),
};
