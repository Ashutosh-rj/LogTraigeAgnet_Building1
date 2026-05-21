"use client";

import Link from "next/link";
import type { Incident } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export function IncidentTable({ incidents, loading }: { incidents?: Incident[]; loading?: boolean }) {
  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  if (!incidents?.length) {
    return <div className="rounded-md border border-border p-8 text-center text-sm text-muted-foreground">No incidents match the current filters.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-3 pr-4">Incident</th>
            <th className="py-3 pr-4">Severity</th>
            <th className="py-3 pr-4">Status</th>
            <th className="py-3 pr-4">Source</th>
            <th className="py-3 pr-4">Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {incidents.map((incident) => (
            <tr key={incident.id} className="hover:bg-muted/60">
              <td className="py-3 pr-4">
                <Link className="font-medium text-primary" href={`/incidents/${incident.id}`}>
                  {incident.title}
                </Link>
                <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{incident.description}</p>
              </td>
              <td className="py-3 pr-4">
                <Badge tone={incident.severity}>{incident.severity}</Badge>
              </td>
              <td className="py-3 pr-4">
                <Badge tone={incident.status}>{incident.status}</Badge>
              </td>
              <td className="py-3 pr-4">{incident.source}</td>
              <td className="py-3 pr-4 text-muted-foreground">
                {new Date(incident.updated_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

