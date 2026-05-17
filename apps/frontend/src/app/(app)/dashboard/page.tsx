"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Activity, Clock, Flame, ShieldAlert } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { IncidentTable } from "@/components/incident-table";
import { StatCard } from "@/components/stat-card";

export default function DashboardPage() {
  const analytics = useQuery({ queryKey: ["analytics"], queryFn: api.analytics });
  const incidents = useQuery({
    queryKey: ["incidents", "dashboard"],
    queryFn: () => api.incidents({ limit: 8 })
  });
  const severityData = Object.entries(analytics.data?.by_severity ?? {}).map(([name, value]) => ({
    name,
    value
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-semibold">Operations Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">Live posture across active incidents and response health.</p>
        </div>
      </div>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <StatCard label="Total incidents" value={analytics.data?.total ?? "—"} icon={ShieldAlert} tone="bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-200" />
        <StatCard label="Open critical" value={analytics.data?.open_critical ?? "—"} icon={Flame} tone="bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-200" />
        <StatCard label="MTTR hours" value={analytics.data?.mean_time_to_resolve_hours ?? "—"} icon={Clock} tone="bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-200" />
        <StatCard label="Live stream" value="On" icon={Activity} tone="bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-200" />
      </motion.div>
      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Severity Distribution</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={severityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" fill="hsl(var(--primary))" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent Incidents</CardTitle>
          </CardHeader>
          <CardContent>
            <IncidentTable incidents={incidents.data?.items} loading={incidents.isLoading} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

