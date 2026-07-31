import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Billing from "./Billing";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { BillingUsage, User } from "../types";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);
const mockedUseAuth = vi.mocked(useAuth);

const FREE_USER: User = { id: "u1", email: "free@example.com", plan: "free", created_at: "2026-01-01T00:00:00Z" };

function mockUsage(usage: BillingUsage) {
  mockedGet.mockResolvedValue({ data: usage });
}

describe("Billing", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedPost.mockReset();
  });

  it("highlights the current plan and shows usage", async () => {
    mockedUseAuth.mockReturnValue({
      user: FREE_USER,
      loading: false,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
    mockUsage({ plan: "free", scans_used_this_month: 2, monthly_scan_limit: 3, aggressive_allowed: false });

    render(<Billing />);

    expect(await screen.findByText(/2 \/ 3 scans used this month/)).toBeInTheDocument();
    const freeCard = screen.getByText("Free").closest("div")!.parentElement!;
    expect(freeCard).toHaveTextContent("Current plan");
  });

  it("shows 'unlimited' once on a plan with no monthly cap", async () => {
    mockedUseAuth.mockReturnValue({
      user: { ...FREE_USER, plan: "pro" },
      loading: false,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
    mockUsage({ plan: "pro", scans_used_this_month: 5, monthly_scan_limit: null, aggressive_allowed: true });

    render(<Billing />);

    expect(await screen.findByText(/5 scans this month \(unlimited\)/)).toBeInTheDocument();
  });

  it("switches plan on click and refreshes both user and usage", async () => {
    const refreshUser = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: FREE_USER,
      loading: false,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      refreshUser,
    });
    mockUsage({ plan: "free", scans_used_this_month: 0, monthly_scan_limit: 3, aggressive_allowed: false });
    mockedPost.mockResolvedValue({ data: { ...FREE_USER, plan: "pro" } });

    const user = userEvent.setup();
    render(<Billing />);

    await screen.findByText(/0 \/ 3 scans used this month/);
    const switchButtons = await screen.findAllByRole("button", { name: "Switch" });
    await user.click(switchButtons[0]); // Pro is the first non-free plan card

    await waitFor(() => expect(mockedPost).toHaveBeenCalledWith("/api/billing/upgrade", { plan: "pro" }));
    await waitFor(() => expect(refreshUser).toHaveBeenCalled());
    expect(mockedGet).toHaveBeenCalledTimes(2); // initial load + reload after switching
  });

  it("asks for confirmation before downgrading to Free, and does nothing on Cancel", async () => {
    const refreshUser = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: { ...FREE_USER, plan: "pro" },
      loading: false,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      refreshUser,
    });
    mockUsage({ plan: "pro", scans_used_this_month: 5, monthly_scan_limit: null, aggressive_allowed: true });

    const user = userEvent.setup();
    render(<Billing />);

    await screen.findByText(/5 scans this month \(unlimited\)/);
    const switchButtons = await screen.findAllByRole("button", { name: "Switch" });
    await user.click(switchButtons[0]); // Free is the first plan card

    expect(await screen.findByText(/drop to 3 scans\/month/)).toBeInTheDocument();
    expect(mockedPost).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText(/drop to 3 scans\/month/)).not.toBeInTheDocument();
    expect(mockedPost).not.toHaveBeenCalled();
  });

  it("downgrades to Free once the user confirms", async () => {
    const refreshUser = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: { ...FREE_USER, plan: "pro" },
      loading: false,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      refreshUser,
    });
    mockUsage({ plan: "pro", scans_used_this_month: 5, monthly_scan_limit: null, aggressive_allowed: true });
    mockedPost.mockResolvedValue({ data: { ...FREE_USER, plan: "free" } });

    const user = userEvent.setup();
    render(<Billing />);

    const switchButtons = await screen.findAllByRole("button", { name: "Switch" });
    await user.click(switchButtons[0]); // Free is the first plan card
    await user.click(await screen.findByRole("button", { name: "Confirm downgrade" }));

    await waitFor(() => expect(mockedPost).toHaveBeenCalledWith("/api/billing/upgrade", { plan: "free" }));
    await waitFor(() => expect(refreshUser).toHaveBeenCalled());
  });
});
