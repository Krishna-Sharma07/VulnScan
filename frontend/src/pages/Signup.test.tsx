import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Signup from "./Signup";
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

function renderSignup() {
  return render(
    <MemoryRouter>
      <Signup />
    </MemoryRouter>
  );
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, password: string, confirm: string) {
  await user.type(screen.getByLabelText("Email"), "new@example.com");
  await user.type(screen.getByLabelText("Password"), password);
  await user.type(screen.getByLabelText("Confirm password"), confirm);
  await user.click(screen.getByRole("button", { name: /sign up/i }));
}

describe("Signup", () => {
  beforeEach(() => {
    navigateSpy.mockClear();
  });

  it("blocks submission client-side when passwords don't match, without calling the API", async () => {
    const signup = vi.fn();
    mockedUseAuth.mockReturnValue({ signup, login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(), user: null, loading: false });
    const user = userEvent.setup();
    renderSignup();

    await fillAndSubmit(user, "testpassword123", "somethingelse");

    expect(await screen.findByText("Passwords do not match")).toBeInTheDocument();
    expect(signup).not.toHaveBeenCalled();
  });

  it("signs up and navigates to /domains on success", async () => {
    const signup = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({ signup, login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(), user: null, loading: false });
    const user = userEvent.setup();
    renderSignup();

    await fillAndSubmit(user, "testpassword123", "testpassword123");

    await waitFor(() => expect(signup).toHaveBeenCalledWith("new@example.com", "testpassword123"));
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith("/domains"));
  });

  it("shows the server's error message when signup fails, without crashing on an array detail", async () => {
    const signup = vi.fn().mockRejectedValue({
      response: { data: { detail: [{ msg: "String should have at least 8 characters" }] } },
    });
    mockedUseAuth.mockReturnValue({ signup, login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(), user: null, loading: false });
    const user = userEvent.setup();
    renderSignup();

    await fillAndSubmit(user, "testpassword123", "testpassword123");

    expect(await screen.findByText("String should have at least 8 characters")).toBeInTheDocument();
  });
});
