import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IncidentTable } from "@/components/incident-table";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>
}));

describe("IncidentTable", () => {
  it("renders incident rows", () => {
    render(
      <IncidentTable
        incidents={[
          {
            id: "incident-1",
            title: "Checkout latency",
            description: "Requests are timing out",
            severity: "high",
            status: "open",
            source: "synthetics",
            tags: [],
            incident_metadata: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ]}
      />
    );

    expect(screen.getByText("Checkout latency")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });
});

