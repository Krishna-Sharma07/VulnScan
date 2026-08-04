import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Domains from "./pages/Domains";
import NewScan from "./pages/NewScan";
import History from "./pages/History";
import ScanDetail from "./pages/ScanDetail";
import Billing from "./pages/Billing";
import CodeScan from "./pages/CodeScan";
import CodeScanDetail from "./pages/CodeScanDetail";

// Logged-out visitors see the marketing landing page at "/"; logged-in
// users are sent straight to their domains instead of seeing it again.
function RootRoute() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-center text-gray-500">Loading...</div>;
  return user ? <Navigate to="/domains" replace /> : <Landing />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<RootRoute />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          <Route element={<ProtectedRoute />}>
            <Route path="/domains" element={<Domains />} />
            <Route path="/scan/new" element={<NewScan />} />
            <Route path="/scan/:id" element={<ScanDetail />} />
            <Route path="/history" element={<History />} />
            <Route path="/code-scan" element={<CodeScan />} />
            <Route path="/code-scan/:id" element={<CodeScanDetail />} />
            <Route path="/billing" element={<Billing />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
