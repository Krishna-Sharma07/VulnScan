import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Domains from "./pages/Domains";
import NewScan from "./pages/NewScan";
import History from "./pages/History";
import ScanDetail from "./pages/ScanDetail";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Navigate to="/domains" replace />} />
            <Route path="/domains" element={<Domains />} />
            <Route path="/scan/new" element={<NewScan />} />
            <Route path="/scan/:id" element={<ScanDetail />} />
            <Route path="/history" element={<History />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
