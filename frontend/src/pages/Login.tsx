import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate("/domains");
    } catch (err) {
      setError(extractErrorMessage(err, "Login failed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto mt-12">
      <h1 className="font-mono text-2xl font-semibold text-ink mb-6">Log in</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="login-email" className="block text-sm font-medium text-muted">
            Email
          </label>
          <input
            id="login-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="login-password" className="block text-sm font-medium text-muted">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
          />
        </div>
        {error && <p className="text-sm text-critical">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-signal text-surface py-2 font-mono font-medium hover:bg-signal-dark disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
        >
          {submitting ? "Logging in..." : "Log in"}
        </button>
      </form>
      <p className="mt-4 text-sm text-muted">
        No account? <Link to="/signup" className="text-signal">Sign up</Link>
      </p>
    </div>
  );
}
