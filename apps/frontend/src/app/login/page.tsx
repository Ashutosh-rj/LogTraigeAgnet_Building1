"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const setSession = useAuthStore((state) => state.setSession);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () =>
      mode === "login" ? api.login(email, password) : api.register(email, name, password),
    onSuccess: (tokens) => {
      setSession(tokens);
      router.replace("/dashboard");
    },
    onError: (err: Error) => setError(err.message)
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
      <section className="flex items-center justify-center bg-card px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          <Card>
            <CardHeader>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <CardTitle>{mode === "login" ? "Sign in to LogIQ" : "Create your workspace account"}</CardTitle>
              <p className="text-sm text-muted-foreground">
                Secure access for incident response, triage, and live operations.
              </p>
            </CardHeader>
            <CardContent>
              <form className="space-y-4" onSubmit={submit}>
                {mode === "register" && (
                  <label className="block space-y-1 text-sm">
                    <span>Name</span>
                    <Input value={name} onChange={(event) => setName(event.target.value)} required />
                  </label>
                )}
                <label className="block space-y-1 text-sm">
                  <span>Email</span>
                  <Input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </label>
                <label className="block space-y-1 text-sm">
                  <span>Password</span>
                  <Input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    minLength={mode === "register" ? 12 : 1}
                  />
                </label>
                {error && <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
                <Button className="w-full" disabled={mutation.isPending}>
                  {mutation.isPending ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
                </Button>
              </form>
              <button
                className="mt-4 text-sm text-primary"
                type="button"
                onClick={() => setMode(mode === "login" ? "register" : "login")}
              >
                {mode === "login" ? "Create an account" : "Use an existing account"}
              </button>
            </CardContent>
          </Card>
        </motion.div>
      </section>
      <section className="hidden items-center justify-center bg-[radial-gradient(circle_at_20%_20%,rgba(20,184,166,0.28),transparent_28%),linear-gradient(135deg,#101828,#123036_48%,#f8fafc)] p-12 lg:flex">
        <div className="max-w-xl text-white">
          <p className="mb-3 text-sm uppercase tracking-[0.24em] text-white/70">Operations Command</p>
          <h1 className="text-5xl font-semibold leading-tight">Incident intelligence for fast, accountable response.</h1>
          <p className="mt-5 text-lg text-white/78">
            Triage signals, search historical context, and keep responders aligned through live event streams.
          </p>
        </div>
      </section>
    </main>
  );
}

