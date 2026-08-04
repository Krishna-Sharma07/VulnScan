import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ScanDetail from "./ScanDetail";
import { api } from "../api/client";
import type { ScanReport } from "../types";

vi.mock("../api/client", () => ({
  api: { get: vi.fn() },
}));

const mockedGet = vi.mocked(api.get);

function baseReport(overrides: Partial<ScanReport> = {}): ScanReport {
  return {
    id: "s1",
    domain_id: "d1",
    target_url: "https://example.com",
    scan_type: "baseline",
    status: "completed",
    created_at: "2026-01-01T00:00:00Z",
    started_at: "2026-01-01T00:01:00Z",
    finished_at: "2026-01-01T00:05:00Z",
    findings: [],
    ...overrides,
  };
}

function renderScanDetail(id = "s1") {
  return render(
    <MemoryRouter initialEntries={[`/scan/${id}`]}>
      <Routes>
        <Route path="/scan/:id" element={<ScanDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ScanDetail", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a loading state before the report arrives", () => {
    mockedGet.mockReturnValue(new Promise(() => {})); // never resolves

    renderScanDetail();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders findings grouped by severity, most severe first, once completed", async () => {
    mockedGet.mockResolvedValue({
      data: baseReport({
        findings: [
          {
            id: "f1",
            vuln_type: "xss_reflected",
            severity: "low",
            title: "Low finding",
            description: "d1",
            evidence: null,
            remediation: "fix1",
            affected_url: "https://example.com/a",
          },
          {
            id: "f2",
            vuln_type: "sql_injection",
            severity: "critical",
            title: "Critical finding",
            description: "d2",
            evidence: null,
            remediation: "fix2",
            affected_url: "https://example.com/b",
          },
        ],
      }),
    });

    renderScanDetail();

    expect(await screen.findByText("2 findings")).toBeInTheDocument();
    expect(screen.getByText("Critical finding")).toBeInTheDocument();
    expect(screen.getByText("Low finding")).toBeInTheDocument();

    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.indexOf("critical")).toBeLessThan(headings.indexOf("low"));
  });

  it("shows a clean-scan message when a completed scan has no findings", async () => {
    mockedGet.mockResolvedValue({ data: baseReport({ status: "completed", findings: [] }) });

    renderScanDetail();

    expect(await screen.findByText("No findings — clean scan.")).toBeInTheDocument();
  });

  it("shows a failure message for failed scans", async () => {
    mockedGet.mockResolvedValue({ data: baseReport({ status: "failed" }) });

    renderScanDetail();

    expect(await screen.findByText("Scan failed. Start a new one to try again.")).toBeInTheDocument();
  });

  it("polls every 3s while pending/running and stops once the scan completes", async () => {
    vi.useFakeTimers();
    mockedGet
      .mockResolvedValueOnce({ data: baseReport({ status: "pending", findings: [] }) })
      .mockResolvedValueOnce({ data: baseReport({ status: "completed", findings: [] }) });

    renderScanDetail();
    await act(async () => {
      await Promise.resolve();
    });
    expect(mockedGet).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(mockedGet).toHaveBeenCalledTimes(2);

    // Status is now "completed" - the interval should have been cleared, so
    // advancing another full tick must not trigger a third fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(mockedGet).toHaveBeenCalledTimes(2);
  });

  it("downloads the PDF report via an authenticated blob request", async () => {
    mockedGet.mockImplementation((url: string) => {
      if (url === "/api/reports/s1") return Promise.resolve({ data: baseReport() });
      if (url === "/api/reports/s1/pdf") return Promise.resolve({ data: new Blob(["pdf-bytes"]) });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    window.URL.createObjectURL = vi.fn().mockReturnValue("blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const user = userEvent.setup();
    renderScanDetail();

    await user.click(await screen.findByRole("button", { name: "Download PDF" }));

    await waitFor(() =>
      expect(mockedGet).toHaveBeenCalledWith("/api/reports/s1/pdf", { responseType: "blob" })
    );
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");

    clickSpy.mockRestore();
  });

  it("alerts when the PDF isn't available yet", async () => {
    mockedGet.mockImplementation((url: string) => {
      if (url === "/api/reports/s1") return Promise.resolve({ data: baseReport() });
      if (url === "/api/reports/s1/pdf") return Promise.reject(new Error("404"));
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const user = userEvent.setup();
    renderScanDetail();

    await user.click(await screen.findByRole("button", { name: "Download PDF" }));

    await waitFor(() => expect(alertSpy).toHaveBeenCalledWith("PDF report not available yet"));

    alertSpy.mockRestore();
  });
});
