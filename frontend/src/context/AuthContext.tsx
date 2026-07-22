import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, clearToken, getToken, setToken } from "../api/client";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On page load, if a token is already in localStorage, ask the API who
  // it belongs to. This is what keeps a user logged in across a refresh.
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get<User>("/api/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    // FastAPI's OAuth2PasswordRequestForm expects form-encoded data with
    // "username"/"password" fields, not JSON - a URLSearchParams body sets
    // the right content-type and shape for that.
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);
    const res = await api.post("/api/auth/login", body);
    setToken(res.data.access_token);
    const me = await api.get<User>("/api/auth/me");
    setUser(me.data);
  }

  async function signup(email: string, password: string) {
    await api.post("/api/auth/signup", { email, password });
    await login(email, password);
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
