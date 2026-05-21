"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import {
  Activity,
  Bell,
  LayoutDashboard,
  LogOut,
  Search,
  Settings,
  ShieldAlert
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { useLiveEvents } from "@/components/use-live-events";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: ShieldAlert },
  { href: "/monitoring", label: "Live", icon: Activity },
  { href: "/search", label: "Search", icon: Search },
  { href: "/admin", label: "Admin", icon: Settings }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const visibleNav = nav.filter((item) => {
    if (item.href === "/admin") return user?.role === "admin";
    return true;
  });
  const isRestoring = useAuthStore((state) => state.isRestoring);
  const logout = useAuthStore((state) => state.logout);
  const refresh = useAuthStore((state) => state.refresh);
  // Prevent refresh() from being called on every render cycle while accessToken
  // is null.  The ref acts as a "refresh already in flight / attempted" guard
  // that survives re-renders but resets on unmount.
  const refreshAttempted = useRef(false);
  useLiveEvents();
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: api.notifications,
    enabled: Boolean(accessToken)
  });

  useEffect(() => {
    if (accessToken || isRestoring) return;
    if (refreshAttempted.current) return;
    refreshAttempted.current = true;
    void refresh().then((restored) => {
      if (!restored) router.replace("/login");
    });
  }, [accessToken, isRestoring, refresh, router]);

  if (!accessToken) return null;

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-card px-4 py-5 lg:block">
        <div className="mb-8 flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <div className="font-semibold">LogIQ</div>
            <div className="text-xs text-muted-foreground">Incident Intelligence</div>
          </div>
        </div>
        <nav className="space-y-1">
          {visibleNav.map((item) => {
            const Icon = item.icon;
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition hover:bg-muted",
                  active && "bg-muted font-medium text-primary"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-4 px-4 lg:px-8">
            <div>
              <div className="text-sm font-medium">{user?.name}</div>
              <div className="text-xs text-muted-foreground">{user?.role}</div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" aria-label="Unread notifications">
                <Bell className="h-4 w-4" />
                {notifications.data?.filter((item) => !item.read_at).length ?? 0}
              </Button>
              <ThemeToggle />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Sign out"
                onClick={() => {
                  void logout().then(() => router.replace("/login"));
                }}
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <nav className="flex gap-2 overflow-x-auto border-t border-border px-4 py-2 lg:hidden">
            {visibleNav.map((item) => (
              <Link key={item.href} href={item.href} className="rounded-md px-3 py-2 text-sm hover:bg-muted">
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
