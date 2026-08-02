import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CodeScan from "./CodeScan";
import { api } from "../api/client";
import type { BillingUsage, CodeScanJob } from "../types";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
  extractErrorMessage: (err: any, fallback: string) => err?.response?.data?.detail ?? fallback,
}));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);

function mockUsageAndHistory(usage: BillingUsage, history: CodeScanJob[] = []) {
  mockedGet.mockImplementation((url: string) => {
    if (url === "/api/billing/usage") return Promise.resolve({ data: usage });
    if (url === "/api/code-scans") return Promise.resolve({ data: history });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderCodeScan() {
  return render(
    <MemoryRouter>
      <CodeScan />
    </MemoryRouter>
  );
}

describe("CodeScan", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedPost.mockReset();
    mockNavigate.mockReset();
  });

  it("submits the selected zip file and navigates to the new scan's detail page", async () => {
    mockUsageAndHistory({
      plan: "free",
      scans_used_this_month: 0,
      monthly_scan_limit: 3,
      aggressive_allowed: false,
    });
    mockedPost.mockResolvedValue({ data: { id: "cs1" } });

    const user = userEvent.setup();
    renderCodeScan();

    const fileInput = await screen.findByLabelText(/code archive/i);
    const file = new File(["zip bytes"], "myproject.zip", { type: "application/zip" });
    await user.upload(fileInput, file);

    await user.click(screen.getByRole("button", { name: /start code scan/i }));

    await waitFor(() => expect(mockedPost).toHaveBeenCalled());
    const [url, formData] = mockedPost.mock.calls[0];
    expect(url).toBe("/api/code-scans");
    expect(formData).toBeInstanceOf(FormData);
    expect(mockNavigate).toHaveBeenCalledWith("/code-scan/cs1");
  });

  it("blocks submission once the shared monthly quota is used up", async () => {
    mockUsageAndHistory({
      plan: "free",
      scans_used_this_month: 3,
      monthly_scan_limit: 3,
      aggressive_allowed: false,
    });
    renderCodeScan();

    expect(
      await screen.findByText(/You've used all 3 scans included in the free plan this month/)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start code scan/i })).toBeDisabled();
  });

  it("lists past code scans with status badges linking to their detail page", async () => {
    mockUsageAndHistory(
      { plan: "free", scans_used_this_month: 1, monthly_scan_limit: 3, aggressive_allowed: false },
      [
        {
          id: "cs1",
          filename: "myproject.zip",
          status: "completed",
          created_at: "2026-01-01T00:00:00Z",
          started_at: null,
          finished_at: null,
        },
      ]
    );

    renderCodeScan();

    expect(await screen.findByText("myproject.zip")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /myproject.zip/ })).toHaveAttribute(
      "href",
      "/code-scan/cs1"
    );
  });

  it("shows an empty state when there is no scan history", async () => {
    mockUsageAndHistory({
      plan: "free",
      scans_used_this_month: 0,
      monthly_scan_limit: 3,
      aggressive_allowed: false,
    });

    renderCodeScan();

    expect(await screen.findByText("No code scans yet.")).toBeInTheDocument();
  });

  it("shows the error message returned by the API when the upload is rejected server-side", async () => {
    mockUsageAndHistory({
      plan: "free",
      scans_used_this_month: 0,
      monthly_scan_limit: 3,
      aggressive_allowed: false,
    });
    mockedPost.mockRejectedValue({ response: { data: { detail: "File is not a valid zip archive" } } });

    const user = userEvent.setup();
    renderCodeScan();

    const fileInput = await screen.findByLabelText(/code archive/i);
    await user.upload(fileInput, new File(["not actually a zip"], "corrupt.zip", { type: "application/zip" }));
    await user.click(screen.getByRole("button", { name: /start code scan/i }));

    expect(await screen.findByText("File is not a valid zip archive")).toBeInTheDocument();
  });
});
