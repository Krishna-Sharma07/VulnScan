import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Billing from "./Billing";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { BillingUsage, User } from "../types";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
  extractErrorMessage: (err: any, fallback: string) => err?.response?.data?.detail ?? fallback,
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
    delete (window as any).Razorpay;
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

  it("starts Razorpay checkout for Pro and applies the plan once payment verifies", async () => {
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
    mockedPost.mockImplementation((url: string) => {
      if (url === "/api/billing/checkout/order") {
        return Promise.resolve({
          data: { order_id: "order_123", amount: 240000, currency: "INR", key_id: "rzp_test_abc" },
        });
      }
      if (url === "/api/billing/checkout/verify") {
        return Promise.resolve({ data: { ...FREE_USER, plan: "pro" } });
      }
      throw new Error(`unexpected POST ${url}`);
    });

    let capturedOptions: any;
    const open = vi.fn();
    (window as any).Razorpay = vi.fn().mockImplementation(function (options: any) {
      capturedOptions = options;
      return { open };
    });

    const user = userEvent.setup();
    render(<Billing />);

    await screen.findByText(/0 \/ 3 scans used this month/);
    await user.click(await screen.findByRole("button", { name: "Upgrade to Pro" }));

    await waitFor(() =>
      expect(mockedPost).toHaveBeenCalledWith("/api/billing/checkout/order", { plan: "pro" })
    );
    expect(open).toHaveBeenCalled();
    expect(capturedOptions.order_id).toBe("order_123");
    expect(capturedOptions.amount).toBe(240000);

    // Simulate Razorpay's popup calling back into our handler after a
    // successful payment - the plan should only change from this, not from
    // the popup merely opening.
    capturedOptions.handler({
      razorpay_order_id: "order_123",
      razorpay_payment_id: "pay_1",
      razorpay_signature: "sig_1",
    });

    await waitFor(() =>
      expect(mockedPost).toHaveBeenCalledWith("/api/billing/checkout/verify", {
        razorpay_order_id: "order_123",
        razorpay_payment_id: "pay_1",
        razorpay_signature: "sig_1",
      })
    );
    await waitFor(() => expect(refreshUser).toHaveBeenCalled());
  });

  it("shows an error and never opens Razorpay if order creation fails", async () => {
    mockedUseAuth.mockReturnValue({
      user: FREE_USER,
      loading: false,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
    mockUsage({ plan: "free", scans_used_this_month: 0, monthly_scan_limit: 3, aggressive_allowed: false });
    mockedPost.mockRejectedValue({ response: { data: { detail: "checkout unavailable" } } });
    const RazorpayCtor = vi.fn();
    (window as any).Razorpay = RazorpayCtor;

    const user = userEvent.setup();
    render(<Billing />);

    await screen.findByText(/0 \/ 3 scans used this month/);
    await user.click(await screen.findByRole("button", { name: "Upgrade to Pro" }));

    expect(await screen.findByText("checkout unavailable")).toBeInTheDocument();
    expect(RazorpayCtor).not.toHaveBeenCalled();
  });

  it("shows a Contact us link for Enterprise instead of a Switch button", async () => {
    mockedUseAuth.mockReturnValue({
      user: FREE_USER,
      loading: false,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
    mockUsage({ plan: "free", scans_used_this_month: 0, monthly_scan_limit: 3, aggressive_allowed: false });

    render(<Billing />);

    await screen.findByText(/0 \/ 3 scans used this month/);
    const contactLink = screen.getByRole("link", { name: "Contact us" });
    expect(contactLink).toHaveAttribute("href", expect.stringContaining("mailto:"));
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
    await user.click(await screen.findByRole("button", { name: "Downgrade to Free" }));

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

    await user.click(await screen.findByRole("button", { name: "Downgrade to Free" }));
    await user.click(await screen.findByRole("button", { name: "Confirm downgrade" }));

    await waitFor(() => expect(mockedPost).toHaveBeenCalledWith("/api/billing/upgrade", { plan: "free" }));
    await waitFor(() => expect(refreshUser).toHaveBeenCalled());
  });
});
