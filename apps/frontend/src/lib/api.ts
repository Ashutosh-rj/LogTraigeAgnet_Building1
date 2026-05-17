import type {
  Incident,
  IncidentAnalytics,
  IncidentStatus,
  LogEntry,
  Notification,
  Page,
  Severity,
  TokenPair,
  User
} from "@/types";
import { useAuthStore } from "@/store/auth-store";

function getApiBaseUrl() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (configured) return configured;
  if (typeof window !== "undefined") {
    if (window.location.hostname === "localhost" && window.location.port === "3000") {
      return "http://localhost:8080";
    }
    return window.location.origin;
  }
  return "http://localhost:8080";
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const token = useAuthStore.getState().accessToken;
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers
    }
  });
  if (response.status === 401 && retry) {
    const refreshed = await useAuthStore.getState().refresh();
    if (refreshed) {
      return request<T>(path, init, false);
    }
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(String(body.detail ?? "Request failed"), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    }),
  register: (email: string, name: string, password: string) =>
    request<TokenPair>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, name, password })
    }),
  refresh: () =>
    request<TokenPair>(
      "/api/v1/auth/refresh",
      { method: "POST" },
      false  // never retry a refresh call to avoid infinite loops
    ),
  logout: () =>
    request<void>(
      "/api/v1/auth/logout",
      { method: "POST" },
      false  // never retry a logout call
    ),
  me: () => request<User>("/api/v1/auth/me"),
  incidents: (params: {
    status?: IncidentStatus | "all";
    severity?: Severity | "all";
    q?: string;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    if (params.status && params.status !== "all") search.set("status", params.status);
    if (params.severity && params.severity !== "all") search.set("severity", params.severity);
    if (params.q) search.set("q", params.q);
    search.set("limit", String(params.limit ?? 20));
    search.set("offset", String(params.offset ?? 0));
    return request<Page<Incident>>(`/api/v1/incidents?${search.toString()}`);
  },
  createIncident: (payload: {
    title: string;
    description: string;
    severity: Severity;
    source: string;
    tags: string[];
  }) =>
    request<Incident>("/api/v1/incidents", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateIncident: (
    id: string,
    payload: Partial<Pick<Incident, "status" | "severity" | "title" | "description" | "assignee_id" | "tags" | "incident_metadata">>
  ) =>
    request<Incident>(`/api/v1/incidents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  incident: (id: string) => request<Incident>(`/api/v1/incidents/${id}`),
  incidentLogs: (id: string) => request<LogEntry[]>(`/api/v1/incidents/${id}/logs`),
  addLog: (id: string, payload: { level: string; message: string; source: string }) =>
    request<LogEntry>(`/api/v1/incidents/${id}/logs`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  triage: (id: string) => request(`/api/v1/incidents/${id}/triage`, { method: "POST" }),
  analytics: () => request<IncidentAnalytics>("/api/v1/analytics/incidents"),
  notifications: () => request<Notification[]>("/api/v1/notifications"),
  search: (query: string) =>
    request<{ results: { owner_type: string; owner_id: string; content: string; score: number }[] }>(
      "/api/v1/search",
      { method: "POST", body: JSON.stringify({ query }) }
    ),
  users: () => request<Page<User>>("/api/v1/users?limit=100&offset=0"),
  auditLogs: () =>
    request<
      {
        id: string;
        actor_id: string | null;
        action: string;
        resource_type: string;
        resource_id: string | null;
        created_at: string;
      }[]
    >("/api/v1/admin/audit-logs")
};
