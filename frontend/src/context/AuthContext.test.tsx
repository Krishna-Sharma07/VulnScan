import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import { api, clearToken, getToken, setToken } from "../api/client";
import type { User } from "../types";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
  getToken: vi.fn(),
  setToken: vi.fn(),
  clearToken: vi.fn(),
}));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);
const mockedGetToken = vi.mocked(getToken);
const mockedSetToken = vi.mocked(setToken);
const mockedClearToken = vi.mocked(clearToken);

const USER: User = { id: "u1", email: "user@example.com", plan: "free", created_at: "2026-01-01T00:00:00Z" };

function renderAuth() {
  return renderHook(() => useAuth(), { wrapper: AuthProvider });
}

describe("AuthContext", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedPost.mockReset();
    mockedGetToken.mockReset();
    mockedSetToken.mockReset();
    mockedClearToken.mockReset();
  });

  it("throws when useAuth is called outside an AuthProvider", () => {
    expect(() => renderHook(() => useAuth())).toThrow("useAuth must be used within AuthProvider");
  });

  it("finishes loading with no user when there is no stored token", async () => {
    mockedGetToken.mockReturnValue(null);

    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("fetches the current user on mount when a token is already stored", async () => {
    mockedGetToken.mockReturnValue("existing-token");
    mockedGet.mockResolvedValue({ data: USER });

    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toEqual(USER);
    expect(mockedGet).toHaveBeenCalledWith("/api/auth/me");
  });

  it("clears a stale token when /me rejects", async () => {
    mockedGetToken.mockReturnValue("stale-token");
    mockedGet.mockRejectedValue(new Error("401"));

    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(mockedClearToken).toHaveBeenCalled();
  });

  it("logs in with a form-encoded body, stores the token, and loads the user", async () => {
    mockedGetToken.mockReturnValue(null);
    mockedPost.mockResolvedValue({ data: { access_token: "tok-abc" } });
    mockedGet.mockResolvedValue({ data: USER });

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("user@example.com", "password123");
    });

    expect(mockedPost).toHaveBeenCalledWith("/api/auth/login", expect.any(URLSearchParams));
    const body = mockedPost.mock.calls[0][1] as URLSearchParams;
    expect(body.get("username")).toBe("user@example.com");
    expect(body.get("password")).toBe("password123");
    expect(mockedSetToken).toHaveBeenCalledWith("tok-abc");
    expect(result.current.user).toEqual(USER);
  });

  it("signs up by posting JSON then logging in with the same credentials", async () => {
    mockedGetToken.mockReturnValue(null);
    mockedPost.mockImplementation((url: string) => {
      if (url === "/api/auth/signup") return Promise.resolve({ data: USER });
      if (url === "/api/auth/login") return Promise.resolve({ data: { access_token: "tok-xyz" } });
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });
    mockedGet.mockResolvedValue({ data: USER });

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.signup("user@example.com", "password123");
    });

    expect(mockedPost).toHaveBeenCalledWith("/api/auth/signup", {
      email: "user@example.com",
      password: "password123",
    });
    expect(mockedSetToken).toHaveBeenCalledWith("tok-xyz");
    expect(result.current.user).toEqual(USER);
  });

  it("logs out by clearing the token and the in-memory user", async () => {
    mockedGetToken.mockReturnValue("tok");
    mockedGet.mockResolvedValue({ data: USER });

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(USER));

    act(() => {
      result.current.logout();
    });

    expect(mockedClearToken).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
  });

  it("refreshUser re-fetches /me so plan changes show up without a page reload", async () => {
    mockedGetToken.mockReturnValue("tok");
    mockedGet.mockResolvedValueOnce({ data: USER }).mockResolvedValueOnce({ data: { ...USER, plan: "pro" } });

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user?.plan).toBe("free"));

    await act(async () => {
      await result.current.refreshUser();
    });

    expect(result.current.user?.plan).toBe("pro");
  });
});
