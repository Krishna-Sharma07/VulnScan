import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./Login";
import { useAuth } from "../context/AuthContext";

vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

const navigateSpy = vi.hoisted(() => vi.fn());
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateSpy };
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  );
}

describe("Login", () => {
  beforeEach(() => {
    navigateSpy.mockClear();
  });

  it("logs in and navigates to /domains on success", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({ login, signup: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(), user: null, loading: false });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "testpassword123");
    await user.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("user@example.com", "testpassword123"));
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith("/domains"));
  });

  it("shows the server's error message on a wrong-password rejection", async () => {
    const login = vi.fn().mockRejectedValue({
      response: { data: { detail: "Incorrect email or password" } },
    });
    mockedUseAuth.mockReturnValue({ login, signup: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(), user: null, loading: false });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /log in/i }));

    expect(await screen.findByText("Incorrect email or password")).toBeInTheDocument();
    expect(navigateSpy).not.toHaveBeenCalled();
  });
});
