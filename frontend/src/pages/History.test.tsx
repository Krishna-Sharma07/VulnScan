import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import History from "./History";
import { api } from "../api/client";
import type { ScanJob, ScanStatus } from "../types";

vi.mock("../api/client", () => ({
  api: { get: vi.fn() },
}));

const mockedGet = vi.mocked(api.get);

function makeScan(overrides: Partial<ScanJob> = {}): ScanJob {
  return {
    id: "s1",
    domain_id: "d1",
    target_url: "https://example.com",
    scan_type: "baseline",
    status: "completed",
    created_at: "2026-01-01T00:00:00Z",
    started_at: null,
    finished_at: null,
    ...overrides,
  };
}

function renderHistory() {
  return render(
    <MemoryRouter>
      <History />
    </MemoryRouter>
  );
}

describe("History", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  it("lists scans with their target, type, and status, linking to the scan detail page", async () => {
    mockedGet.mockResolvedValue({ data: [makeScan({ id: "s1", target_url: "https://x.com" })] });

    renderHistory();

    expect(await screen.findByText("https://x.com")).toBeInTheDocument();
    expect(screen.getByText(/baseline/)).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/scan/s1");
  });

  it("shows an empty state linking to start a new scan when there are none", async () => {
    mockedGet.mockResolvedValue({ data: [] });

    renderHistory();

    expect(await screen.findByText(/No scans yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "start one" })).toHaveAttribute("href", "/scan/new");
  });

  it.each<[ScanStatus, string]>([
    ["pending", "bg-gray-100"],
    ["running", "bg-blue-100"],
    ["completed", "bg-green-100"],
    ["failed", "bg-red-100"],
  ])("gives %s scans the expected status badge color", async (status, expectedClass) => {
    mockedGet.mockResolvedValue({ data: [makeScan({ status })] });

    renderHistory();

    const badge = await screen.findByText(status);
    expect(badge.className).toContain(expectedClass);
  });
});
