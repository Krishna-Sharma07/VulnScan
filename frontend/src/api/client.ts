import axios from "axios";

const TOKEN_KEY = "vulnscan_token";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});

// Runs before every request this instance sends - attaches the JWT from
// localStorage as an Authorization header, so individual API calls never
// have to remember to do it themselves.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// If the token is missing/expired, every protected endpoint replies 401.
// Catching it in one place means "log the user out and send them to
// /login" doesn't need to be repeated in every page that calls the API.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// FastAPI sends two different shapes under the same `detail` key: a plain
// string for errors we raise ourselves (HTTPException), or an array of
// {msg, loc, ...} objects for Pydantic validation failures (422s) - e.g. the
// signup password-length check. Rendering that array directly as a React
// child throws ("Objects are not valid as a React child"), so every catch
// block should go through this instead of reading err.response?.data?.detail
// itself.
export function extractErrorMessage(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg ?? String(d)).join(", ");
  }
  return fallback;
}
