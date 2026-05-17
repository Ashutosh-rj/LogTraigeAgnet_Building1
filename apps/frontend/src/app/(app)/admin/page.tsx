"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Shield, UserCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminPage() {
  const user = useAuthStore((state) => state.user);
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: ["users"], queryFn: api.users, enabled: user?.role === "admin" });
  const audit = useQuery({ queryKey: ["audit"], queryFn: api.auditLogs, enabled: user?.role === "admin" });
  const refreshUsers = useMutation({
    mutationFn: api.users,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] })
  });

  if (user?.role !== "admin") {
    return (
      <Card>
        <CardContent className="p-8 text-sm text-muted-foreground">
          Admin controls are restricted to administrators.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-semibold">Admin Controls</h1>
          <p className="mt-1 text-sm text-muted-foreground">Manage user access and inspect audit activity.</p>
        </div>
        <Button variant="secondary" onClick={() => refreshUsers.mutate()}>
          <UserCheck className="h-4 w-4" />
          Refresh
        </Button>
      </div>
      <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-primary" />
              Users
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {users.data?.items.map((item) => (
              <div key={item.id} className="rounded-md border border-border p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{item.name}</span>
                  <Badge tone="neutral">{item.role}</Badge>
                </div>
                <p className="mt-1 text-muted-foreground">{item.email}</p>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Audit Log</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-3 pr-4">Action</th>
                    <th className="py-3 pr-4">Resource</th>
                    <th className="py-3 pr-4">Actor</th>
                    <th className="py-3 pr-4">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {audit.data?.map((row) => (
                    <tr key={row.id}>
                      <td className="py-3 pr-4 font-medium">{row.action}</td>
                      <td className="py-3 pr-4">{row.resource_type}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{row.actor_id ?? "system"}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{new Date(row.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

