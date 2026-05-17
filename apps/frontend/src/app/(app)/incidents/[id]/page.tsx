"use client";

import { FormEvent, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Send } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [logLevel, setLogLevel] = useState<"debug" | "info" | "warning" | "error" | "critical">("error");
  const incident = useQuery({ queryKey: ["incident", id], queryFn: () => api.incident(id) });
  const logs = useQuery({ queryKey: ["incident-logs", id], queryFn: () => api.incidentLogs(id) });
  const addLog = useMutation({
    mutationFn: () => api.addLog(id, { level: logLevel, message, source: "operator" }),
    onSuccess: () => {
      setMessage("");
      queryClient.invalidateQueries({ queryKey: ["incident-logs", id] });
    }
  });
  const triage = useMutation({
    mutationFn: () => api.triage(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident", id] });
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    addLog.mutate();
  }

  if (incident.isLoading) return <Skeleton className="h-96 w-full" />;
  if (!incident.data) return <div className="text-sm text-muted-foreground">Incident not found.</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="mb-2 flex gap-2">
            <Badge tone={incident.data.severity}>{incident.data.severity}</Badge>
            <Badge tone={incident.data.status}>{incident.data.status}</Badge>
          </div>
          <h1 className="text-3xl font-semibold">{incident.data.title}</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{incident.data.description}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Button onClick={() => triage.mutate()} disabled={triage.isPending}>
            <Bot className="h-4 w-4" />
            {triage.isPending ? "Generating..." : "Generate triage"}
          </Button>
          {triage.isError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              Triage failed: {triage.error?.message ?? "Unknown error"}
            </div>
          )}
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <Card>
          <CardHeader>
            <CardTitle>AI Triage</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h2 className="text-sm font-medium">Summary</h2>
              <p className="mt-2 text-sm text-muted-foreground">{incident.data.summary ?? "No triage report generated yet."}</p>
            </div>
            <div>
              <h2 className="text-sm font-medium">Root Cause</h2>
              <p className="mt-2 text-sm text-muted-foreground">{incident.data.root_cause ?? "Generate a triage report after attaching logs."}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Log Ingestion</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form className="flex gap-2" onSubmit={submit}>
              <select
                value={logLevel}
                onChange={(event) => setLogLevel(event.target.value as typeof logLevel)}
                className="rounded-md border border-input bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                aria-label="Log level"
              >
                <option value="debug">debug</option>
                <option value="info">info</option>
                <option value="warning">warning</option>
                <option value="error">error</option>
                <option value="critical">critical</option>
              </select>
              <Input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Attach log signal" required />
              <Button size="icon" aria-label="Add log" disabled={addLog.isPending}>
                <Send className="h-4 w-4" />
              </Button>
            </form>
            <div className="space-y-3">
              {logs.data?.map((log) => (
                <div key={log.id} className="rounded-md border border-border p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <Badge tone={log.level === "critical" ? "critical" : log.level === "error" ? "high" : "neutral"}>{log.level}</Badge>
                    <span className="text-xs text-muted-foreground">{new Date(log.observed_at).toLocaleString()}</span>
                  </div>
                  <p className="mt-2">{log.message}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{log.source}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

