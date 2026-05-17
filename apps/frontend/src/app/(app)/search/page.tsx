"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const search = useMutation({ mutationFn: () => api.search(query) });

  function submit(event: FormEvent) {
    event.preventDefault();
    search.mutate();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Semantic Search</h1>
        <p className="mt-1 text-sm text-muted-foreground">Find similar incidents, logs, and triage reports through pgvector embeddings.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Search Knowledge Graph</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <form className="flex flex-col gap-3 sm:flex-row" onSubmit={submit}>
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Example: checkout timeout database saturation" minLength={2} required />
            <Button disabled={search.isPending}>
              <Search className="h-4 w-4" />
              Search
            </Button>
          </form>
          <div className="space-y-3">
            {search.data?.results.map((result) => (
              <article key={`${result.owner_type}-${result.owner_id}`} className="rounded-md border border-border p-4">
                <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                  <span>{result.owner_type}</span>
                  <span>{Math.round(result.score * 100)}% match</span>
                </div>
                <p className="mt-2 text-sm">{result.content}</p>
              </article>
            ))}
            {search.error && <p className="text-sm text-destructive">{search.error.message}</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

