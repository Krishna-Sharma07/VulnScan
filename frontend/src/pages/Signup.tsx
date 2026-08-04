import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    // Checked client-side for immediate feedback, but the API's own
    // min_length=8 (app/schemas/user.py) is the real guard - this form
    // isn't the only way to reach POST /api/auth/signup.
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setSubmitting(true);
    try {
      await signup(email.trim(), password);
      navigate("/domains");
    } catch (err) {
      setError(extractErrorMessage(err, "Signup failed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto mt-12">
      <h1 className="font-mono text-2xl font-semibold text-ink mb-6">Create an account</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="signup-email" className="block text-sm font-medium text-muted">
            Email
          </label>
          <input
            id="signup-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="signup-password" className="block text-sm font-medium text-muted">
            Password
          </label>
          <input
            id="signup-password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
          />
          <p className="mt-1 text-xs text-muted">At least 8 characters</p>
        </div>
        <div>
          <label htmlFor="signup-confirm-password" className="block text-sm font-medium text-muted">
            Confirm password
          </label>
          <input
            id="signup-confirm-password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1 w-full border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
          />
        </div>
        {error && <p className="text-sm text-critical">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-signal text-surface py-2 font-mono font-medium hover:bg-signal-dark disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
        >
          {submitting ? "Creating account..." : "Sign up"}
        </button>
      </form>
      <p className="mt-4 text-sm text-muted">
        Already have an account? <Link to="/login" className="text-signal">Log in</Link>
      </p>
    </div>
  );
}
