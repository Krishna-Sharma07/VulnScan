import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-100"
  }`;

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 flex items-center justify-between h-14">
          <Link to="/" className="font-semibold text-indigo-600">
            VulnScan Pro
          </Link>
          {user && (
            <div className="flex items-center gap-1">
              <NavLink to="/domains" className={navLinkClass}>
                Domains
              </NavLink>
              <NavLink to="/scan/new" className={navLinkClass}>
                New Scan
              </NavLink>
              <NavLink to="/history" className={navLinkClass}>
                History
              </NavLink>
              <span className="text-sm text-gray-400 mx-2">{user.email}</span>
              <button
                onClick={logout}
                className="px-3 py-2 rounded-md text-sm font-medium text-gray-600 hover:bg-gray-100"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
