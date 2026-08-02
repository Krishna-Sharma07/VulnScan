import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CodeScanDetail from "./CodeScanDetail";
import { api } from "../api/client";
import type { CodeScanReport } from "../types";

vi.mock("../api/client", () => ({
  api: { get: vi.fn() },
}));

const mockedGet = vi.mocked(api.get);

function baseReport(overrides: Partial<CodeScanReport> = {}): CodeScanReport {
  return {
    id: "cs1",
    filename: "myproject.zip",
    status: "completed",
    created_at: "2026-01-01T00:00:00Z",
    started_at: "2026-01-01T00:01:00Z",
    finished_at: "2026-01-01T00:05:00Z",
    findings: [],
    ...overrides,
  };
}

function renderCodeScanDetail(id = "cs1") {
  return render(
    <MemoryRouter initialEntries={[`/code-scan/${id}`]}>
      <Routes>
        <Route path="/code-scan/:id" element={<CodeScanDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("CodeScanDetail", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a loading state before the report arrives", () => {
    mockedGet.mockReturnValue(new Promise(() => {}));

    renderCodeScanDetail();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders findings grouped by severity with source and file:line location", async () => {
    mockedGet.mockResolvedValue({
      data: baseReport({
        findings: [
          {
            id: "f1",
            source: "bandit",
            vuln_type: "B105",
            severity: "medium",
            title: "hardcoded_password_string",
            description: "Possible hardcoded password",
            evidence: null,
            remediation: "Review and remediate the flagged code pattern.",
            affected_file: "src/app.py",
            line_number: 12,
          },
          {
            id: "f2",
            source: "safety",
            vuln_type: "12345",
            severity: "critical",
            title: "Vulnerable dependency: django 2.2.0",
            description: "Known SQL injection vulnerability",
            evidence: "<2.2.28",
            remediation: "Upgrade the package to a version outside the vulnerable range.",
            affected_file: "requirements.txt",
            line_number: null,
          },
        ],
      }),
    });

    renderCodeScanDetail();

    expect(await screen.findByText("2 findings")).toBeInTheDocument();
    expect(screen.getByText("src/app.py:12")).toBeInTheDocument();
    expect(screen.getByText("requirements.txt")).toBeInTheDocument();

    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.indexOf("critical")).toBeLessThan(headings.indexOf("medium"));
  });

  it("shows a clean-scan message when a completed scan has no findings", async () => {
    mockedGet.mockResolvedValue({ data: baseReport({ status: "completed", findings: [] }) });

    renderCodeScanDetail();

    expect(await screen.findByText("No findings — clean scan.")).toBeInTheDocument();
  });

  it("shows a failure message for failed scans", async () => {
    mockedGet.mockResolvedValue({ data: baseReport({ status: "failed" }) });

    renderCodeScanDetail();

    expect(await screen.findByText("Scan failed. Try uploading again.")).toBeInTheDocument();
  });

  it("polls every 3s while pending/running and stops once the scan completes", async () => {
    vi.useFakeTimers();
    mockedGet
      .mockResolvedValueOnce({ data: baseReport({ status: "pending", findings: [] }) })
      .mockResolvedValueOnce({ data: baseReport({ status: "completed", findings: [] }) });

    renderCodeScanDetail();
    await act(async () => {
      await Promise.resolve();
    });
    expect(mockedGet).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(mockedGet).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(mockedGet).toHaveBeenCalledTimes(2);
  });

  it("downloads the PDF report via an authenticated blob request", async () => {
    mockedGet.mockImplementation((url: string) => {
      if (url === "/api/code-scans/cs1") return Promise.resolve({ data: baseReport() });
      if (url === "/api/code-scans/cs1/pdf") return Promise.resolve({ data: new Blob(["pdf-bytes"]) });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    window.URL.createObjectURL = vi.fn().mockReturnValue("blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const user = userEvent.setup();
    renderCodeScanDetail();

    await user.click(await screen.findByRole("button", { name: "Download PDF" }));

    await waitFor(() =>
      expect(mockedGet).toHaveBeenCalledWith("/api/code-scans/cs1/pdf", { responseType: "blob" })
    );
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");

    clickSpy.mockRestore();
  });

  it("alerts when the PDF isn't available yet", async () => {
    mockedGet.mockImplementation((url: string) => {
      if (url === "/api/code-scans/cs1") return Promise.resolve({ data: baseReport() });
      if (url === "/api/code-scans/cs1/pdf") return Promise.reject(new Error("404"));
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    const user = userEvent.setup();
    renderCodeScanDetail();

    await user.click(await screen.findByRole("button", { name: "Download PDF" }));

    await waitFor(() => expect(alertSpy).toHaveBeenCalledWith("PDF report not available yet"));

    alertSpy.mockRestore();
  });
});
