import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Domains from "./Domains";
import { api } from "../api/client";
import type { Domain } from "../types";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);
const mockedPut = vi.mocked(api.put);

function makeDomain(overrides: Partial<Domain> = {}): Domain {
  return {
    id: "d1",
    hostname: "example.com",
    verification_token: "tok-abc123",
    verified: false,
    has_auth_cookie: false,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("Domains", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedPost.mockReset();
    mockedPut.mockReset();
  });

  it("renders verified domains with a badge and unverified ones with DNS instructions", async () => {
    mockedGet.mockResolvedValue({
      data: [
        makeDomain({ id: "d1", hostname: "verified.com", verified: true }),
        makeDomain({ id: "d2", hostname: "pending.com", verified: false, verification_token: "tok-xyz" }),
      ],
    });

    render(<Domains />);

    expect(await screen.findByText("verified.com")).toBeInTheDocument();
    expect(screen.getByText("[Verified]")).toBeInTheDocument();
    // "pending.com" legitimately appears twice: the domain row itself, and
    // again inside its "add this DNS TXT record" instructions.
    expect(screen.getAllByText("pending.com")).toHaveLength(2);
    expect(screen.getByText(/vulnscan-verify=tok-xyz/)).toBeInTheDocument();
  });

  it("shows an empty state when there are no domains", async () => {
    mockedGet.mockResolvedValue({ data: [] });

    render(<Domains />);

    expect(await screen.findByText(/No domains yet/)).toBeInTheDocument();
  });

  it("adds a domain and reloads the list", async () => {
    let store: Domain[] = [];
    mockedGet.mockImplementation(() => Promise.resolve({ data: store }));
    mockedPost.mockImplementation((url: string, body: any) => {
      if (url === "/api/domains") {
        store = [...store, makeDomain({ id: "new1", hostname: body.hostname })];
        return Promise.resolve({ data: store[store.length - 1] });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    const user = userEvent.setup();
    render(<Domains />);
    await screen.findByText(/No domains yet/);

    await user.type(screen.getByPlaceholderText("example.com"), "new.com");
    await user.click(screen.getByRole("button", { name: "Add domain" }));

    // Appears twice once added: the domain row, and again inside its
    // unverified-domain DNS instructions.
    await waitFor(() => expect(screen.getAllByText("new.com")).toHaveLength(2));
    expect(mockedPost).toHaveBeenCalledWith("/api/domains", { hostname: "new.com" });
  });

  it("shows the server's error message when adding a domain fails", async () => {
    mockedGet.mockResolvedValue({ data: [] });
    mockedPost.mockRejectedValue({ response: { data: { detail: "Domain already registered" } } });

    const user = userEvent.setup();
    render(<Domains />);
    await screen.findByText(/No domains yet/);

    await user.type(screen.getByPlaceholderText("example.com"), "dup.com");
    await user.click(screen.getByRole("button", { name: "Add domain" }));

    expect(await screen.findByText("Domain already registered")).toBeInTheDocument();
  });

  it("checks verification and shows the Verified badge on success", async () => {
    let store = [makeDomain({ id: "d1", hostname: "pending.com", verified: false })];
    mockedGet.mockImplementation(() => Promise.resolve({ data: store }));
    mockedPost.mockImplementation((url: string) => {
      if (url === "/api/domains/d1/verify") {
        store = store.map((d) => (d.id === "d1" ? { ...d, verified: true } : d));
        return Promise.resolve({ data: {} });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });

    const user = userEvent.setup();
    render(<Domains />);

    await user.click(await screen.findByRole("button", { name: "Check verification" }));

    expect(await screen.findByText("[Verified]")).toBeInTheDocument();
  });

  it("shows an error under the domain when verification fails", async () => {
    mockedGet.mockResolvedValue({ data: [makeDomain({ id: "d1", verified: false })] });
    mockedPost.mockRejectedValue({ response: { data: { detail: "DNS record not found" } } });

    const user = userEvent.setup();
    render(<Domains />);

    await user.click(await screen.findByRole("button", { name: "Check verification" }));

    expect(await screen.findByText("DNS record not found")).toBeInTheDocument();
  });

  it("saves an auth cookie and reflects it as set", async () => {
    let store = [makeDomain({ id: "d1", verified: true, has_auth_cookie: false })];
    mockedGet.mockImplementation(() => Promise.resolve({ data: store }));
    mockedPut.mockImplementation((url: string, body: any) => {
      store = store.map((d) => (d.id === "d1" ? { ...d, has_auth_cookie: !!body.auth_cookie } : d));
      return Promise.resolve({ data: {} });
    });

    const user = userEvent.setup();
    render(<Domains />);

    await user.click(await screen.findByRole("button", { name: "Set cookie" }));
    await user.type(screen.getByPlaceholderText(/security=low/), "PHPSESSID=abc123");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockedPut).toHaveBeenCalledWith("/api/domains/d1/auth-cookie", {
        auth_cookie: "PHPSESSID=abc123",
      })
    );
    expect(await screen.findByText("Cookie set.")).toBeInTheDocument();
  });

  it("clears an existing auth cookie", async () => {
    let store = [makeDomain({ id: "d1", verified: true, has_auth_cookie: true })];
    mockedGet.mockImplementation(() => Promise.resolve({ data: store }));
    mockedPut.mockImplementation((url: string, body: any) => {
      store = store.map((d) => (d.id === "d1" ? { ...d, has_auth_cookie: !!body.auth_cookie } : d));
      return Promise.resolve({ data: {} });
    });

    const user = userEvent.setup();
    render(<Domains />);

    expect(await screen.findByRole("button", { name: "Update" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear cookie" }));

    await waitFor(() =>
      expect(mockedPut).toHaveBeenCalledWith("/api/domains/d1/auth-cookie", { auth_cookie: null })
    );
    expect(await screen.findByText("None set.")).toBeInTheDocument();
  });

  it("cancelling the cookie form discards the input without saving", async () => {
    mockedGet.mockResolvedValue({ data: [makeDomain({ id: "d1", verified: true, has_auth_cookie: false })] });

    const user = userEvent.setup();
    render(<Domains />);

    await user.click(await screen.findByRole("button", { name: "Set cookie" }));
    await user.type(screen.getByPlaceholderText(/security=low/), "some-value");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByPlaceholderText(/security=low/)).not.toBeInTheDocument();
    expect(mockedPut).not.toHaveBeenCalled();
  });
});
