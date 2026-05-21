"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Radio } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function MonitoringPage() {
  const incidents = useQuery({
    queryKey: ["incidents", "live"],
    queryFn: () => api.incidents({ status: "open", limit: 20 }),
    refetchInterval: 30_000
  });
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: api.notifications,
    refetchInterval: 30_000
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Live Monitoring</h1>
        <p className="mt-1 text-sm text-muted-foreground">WebSocket-backed operations feed with polling as a resilient fallback.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-primary" />
              Active Incident Stream
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {incidents.isLoading && <Skeleton className="h-40 w-full" />}
            {incidents.data?.items.map((incident) => (
              <div key={incident.id} className="rounded-md border border-border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={incident.severity}>{incident.severity}</Badge>
                  <Badge tone={incident.status}>{incident.status}</Badge>
                  <span className="text-xs text-muted-foreground">{incident.source}</span>
                </div>
                <h2 className="mt-3 font-medium">{incident.title}</h2>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{incident.description}</p>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              Notifications
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {notifications.data?.map((notification) => (
              <div key={notification.id} className="rounded-md border border-border p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{notification.title}</span>
                  {!notification.read_at && <span className="h-2 w-2 rounded-full bg-primary" />}
                </div>
                <p className="mt-1 text-muted-foreground">{notification.message}</p>
              </div>
            ))}
            {notifications.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">No notifications yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

