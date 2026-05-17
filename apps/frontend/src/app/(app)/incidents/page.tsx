"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import type { IncidentStatus, Severity } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { IncidentTable } from "@/components/incident-table";

const severities: (Severity | "all")[] = ["all", "critical", "high", "medium", "low"];
const statuses: (IncidentStatus | "all")[] = ["all", "open", "investigating", "resolved", "closed"];

export default function IncidentsPage() {
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<IncidentStatus | "all">("all");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const incidents = useQuery({
    queryKey: ["incidents", { q, severity, status }],
    queryFn: () => api.incidents({ q, severity, status, limit: 40 })
  });
  const create = useMutation({
    mutationFn: () =>
      api.createIncident({
        title,
        description,
        severity: severity === "all" ? "medium" : severity,
        source: "dashboard",
        tags: q ? [q] : []
      }),
    onSuccess: () => {
      setTitle("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Incidents</h1>
        <p className="mt-1 text-sm text-muted-foreground">Create, filter, assign, and resolve operational work.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle>Incident Queue</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-[1fr_180px_180px]">
              <label className="relative">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input className="pl-9" placeholder="Search incidents" value={q} onChange={(event) => setQ(event.target.value)} />
              </label>
              <select className="h-10 rounded-md border border-border bg-background px-3 text-sm" value={severity} onChange={(event) => setSeverity(event.target.value as Severity | "all")}>
                {severities.map((item) => <option key={item}>{item}</option>)}
              </select>
              <select className="h-10 rounded-md border border-border bg-background px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value as IncidentStatus | "all")}>
                {statuses.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
            <IncidentTable incidents={incidents.data?.items} loading={incidents.isLoading} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>New Incident</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={submit}>
              <Input placeholder="Title" value={title} onChange={(event) => setTitle(event.target.value)} required minLength={3} />
              <textarea className="min-h-32 w-full rounded-md border border-border bg-background p-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="Description" value={description} onChange={(event) => setDescription(event.target.value)} required minLength={5} />
              <Button className="w-full" disabled={create.isPending}>
                <Plus className="h-4 w-4" />
                {create.isPending ? "Creating..." : "Create incident"}
              </Button>
              {create.error && <p className="text-sm text-destructive">{create.error.message}</p>}
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

