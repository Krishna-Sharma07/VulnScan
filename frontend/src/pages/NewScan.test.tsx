import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewScan from "./NewScan";
import { api } from "../api/client";
import type { BillingUsage, Domain } from "../types";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

const mockedGet = vi.mocked(api.get);

const VERIFIED_DOMAIN: Domain = {
  id: "domain-1",
  hostname: "example.com",
  verification_token: "tok",
  verified: true,
  has_auth_cookie: false,
  created_at: "2026-01-01T00:00:00Z",
};

function mockDomainsAndUsage(usage: BillingUsage, domains: Domain[] = [VERIFIED_DOMAIN]) {
  mockedGet.mockImplementation((url: string) => {
    if (url === "/api/domains") return Promise.resolve({ data: domains });
    if (url === "/api/billing/usage") return Promise.resolve({ data: usage });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderNewScan() {
  return render(
    <MemoryRouter>
      <NewScan />
    </MemoryRouter>
  );
}

describe("NewScan", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  it("shows the aggressive-scan upgrade hint and leaves quota alone on the free plan", async () => {
    mockDomainsAndUsage({
      plan: "free",
      scans_used_this_month: 1,
      monthly_scan_limit: 3,
      aggressive_allowed: false,
    });
    renderNewScan();

    expect(await screen.findByText(/Aggressive scans require Pro or Enterprise/)).toBeInTheDocument();
    expect(screen.queryByText(/scans included in the free plan/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start scan/i })).toBeEnabled();
  });

  it("blocks submission once the free plan's monthly quota is used up", async () => {
    mockDomainsAndUsage({
      plan: "free",
      scans_used_this_month: 3,
      monthly_scan_limit: 3,
      aggressive_allowed: false,
    });
    renderNewScan();

    expect(
      await screen.findByText(/You've used all 3 scans included in the free plan this month/)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start scan/i })).toBeDisabled();
  });

  it("shows no gating warnings on a Pro plan with unlimited scans", async () => {
    mockDomainsAndUsage({
      plan: "pro",
      scans_used_this_month: 10,
      monthly_scan_limit: null,
      aggressive_allowed: true,
    });
    renderNewScan();

    await waitFor(() => expect(screen.getByRole("combobox", { name: /domain/i })).toBeInTheDocument());
    expect(screen.queryByText(/Aggressive scans require Pro or Enterprise/)).not.toBeInTheDocument();
    expect(screen.queryByText(/scans included in the free plan/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start scan/i })).toBeEnabled();
  });

  it("prompts to add a verified domain when none exist yet", async () => {
    mockDomainsAndUsage(
      { plan: "free", scans_used_this_month: 0, monthly_scan_limit: 3, aggressive_allowed: false },
      []
    );
    renderNewScan();

    expect(
      await screen.findByText(/You need at least one verified domain/)
    ).toBeInTheDocument();
  });
});
