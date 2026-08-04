import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 text-sm font-mono ${
    isActive ? "bg-signal text-surface" : "text-muted hover:bg-paper"
  }`;

const navLinks = [
  { to: "/domains", label: "Domains" },
  { to: "/scan/new", label: "New Scan" },
  { to: "/code-scan", label: "Code Scan" },
  { to: "/history", label: "History" },
  { to: "/billing", label: "Billing" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  // Below md, there isn't room for five nav links plus the email/plan badge
  // and logout button in one row, so they collapse behind a hamburger
  // button instead (Tailwind breakpoint + conditional render - no extra
  // library, matching how the rest of the app is built).
  return (
    <div className="min-h-screen bg-paper">
      <nav className="bg-surface border-b border-hairline">
        <div className="max-w-5xl mx-auto px-4 flex items-center justify-between h-14">
          <Link to="/" className="font-mono font-semibold text-signal">
            VulnScan Pro
          </Link>
          {user && (
            <>
              <div className="hidden md:flex items-center gap-1">
                {navLinks.map((link) => (
                  <NavLink key={link.to} to={link.to} className={navLinkClass}>
                    {link.label}
                  </NavLink>
                ))}
                <span className="font-mono text-xs text-muted mx-2">
                  {user.email}{" "}
                  <span className="uppercase font-semibold text-signal">{user.plan}</span>
                </span>
                <button
                  onClick={logout}
                  className="px-3 py-2 text-sm font-mono text-muted hover:bg-paper focus:ring-2 focus:ring-signal focus:outline-none"
                >
                  Log out
                </button>
              </div>
              <button
                onClick={() => setMenuOpen((open) => !open)}
                aria-label="Toggle menu"
                aria-expanded={menuOpen}
                className="md:hidden p-2 text-muted hover:bg-paper focus:ring-2 focus:ring-signal focus:outline-none"
              >
                {menuOpen ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                )}
              </button>
            </>
          )}
        </div>
        {user && menuOpen && (
          <div className="md:hidden border-t border-hairline px-4 py-3 space-y-1">
            {navLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `block px-3 py-2 text-sm font-mono ${
                    isActive ? "bg-signal text-surface" : "text-muted hover:bg-paper"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
            <div className="font-mono text-xs text-muted px-3 pt-2">
              {user.email} <span className="uppercase font-semibold text-signal">{user.plan}</span>
            </div>
            <button
              onClick={() => {
                setMenuOpen(false);
                logout();
              }}
              className="block w-full text-left px-3 py-2 text-sm font-mono text-muted hover:bg-paper"
            >
              Log out
            </button>
          </div>
        )}
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
