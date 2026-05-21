export type Role = "admin" | "responder" | "viewer";
export type Severity = "critical" | "high" | "medium" | "low";
export type IncidentStatus = "open" | "investigating" | "resolved" | "closed";
export type LogLevel = "debug" | "info" | "warning" | "error" | "critical";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  source: string;
  assignee_id?: string | null;
  created_by_id?: string | null;
  summary?: string | null;
  root_cause?: string | null;
  tags: string[];
  incident_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface LogEntry {
  id: string;
  incident_id: string;
  level: LogLevel;
  message: string;
  source: string;
  observed_at: string;
}

export interface Notification {
  id: string;
  title: string;
  message: string;
  kind: string;
  incident_id?: string | null;
  read_at?: string | null;
  created_at: string;
}

export interface IncidentAnalytics {
  total: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  open_critical: number;
  mean_time_to_resolve_hours: number | null;
}

