/**
 * services/api.js
 *
 * Central Axios instance for the school portal.
 *
 * Features:
 *  - Attaches Bearer token to every request automatically
 *  - On 401: silently refreshes token and retries the failed request once
 *  - On refresh failure: clears auth state and redirects to /login
 *  - Exports focused API modules: authAPI, schoolAPI
 */

import axios from "axios";

const BASE_URL = process.env.REACT_APP_API_URL || "";

// ── Token storage helpers ──────────────────────────────────────────────────
// Tokens live in memory (access) + localStorage (refresh only).
// Never store access tokens in localStorage — XSS risk.

let _accessToken = null;

export const tokenStore = {
  getAccess:      ()      => _accessToken,
  setAccess:      (token) => { _accessToken = token; },
  clearAccess:    ()      => { _accessToken = null; },

  getRefresh:     ()      => localStorage.getItem("refresh_token"),
  setRefresh:     (token) => localStorage.setItem("refresh_token", token),
  clearRefresh:   ()      => localStorage.removeItem("refresh_token"),

  setTokens: ({ access, refresh }) => {
    _accessToken = access;
    if (refresh) localStorage.setItem("refresh_token", refresh);
  },
  clearAll: () => {
    _accessToken = null;
    localStorage.removeItem("refresh_token");
  },
};

// ── Axios instance ─────────────────────────────────────────────────────────

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

// ── Request interceptor: attach access token ───────────────────────────────

api.interceptors.request.use(
  (config) => {
    const token = tokenStore.getAccess();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor: auto-refresh on 401 ─────────────────────────────

let _refreshPromise = null; // deduplicate concurrent refresh calls

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    // Only attempt refresh on 401 and only once per request
    if (
      error.response?.status === 401 &&
      !original._retried &&
      !original.url?.includes("/api/auth/token/refresh/")
    ) {
      original._retried = true;

      try {
        // Deduplicate: if a refresh is already in flight, wait for it
        if (!_refreshPromise) {
          _refreshPromise = _refreshAccessToken().finally(() => {
            _refreshPromise = null;
          });
        }
        await _refreshPromise;

        // Retry original request with new token
        original.headers.Authorization = `Bearer ${tokenStore.getAccess()}`;
        return api(original);
      } catch {
        // Refresh failed — force logout
        tokenStore.clearAll();
        // Dispatch a custom event so AuthContext can react without a circular import
        window.dispatchEvent(new CustomEvent("auth:logout"));
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

// ── Token refresh helper ───────────────────────────────────────────────────

async function _refreshAccessToken() {
  const refresh = tokenStore.getRefresh();
  if (!refresh) throw new Error("No refresh token available.");

  const response = await axios.post(`${BASE_URL}/api/auth/token/refresh/`, {
    refresh,
  });

  const { access, refresh: newRefresh } = response.data;
  tokenStore.setAccess(access);
  if (newRefresh) tokenStore.setRefresh(newRefresh);

  return access;
}

// ── Focused API modules ────────────────────────────────────────────────────

export const authAPI = {
  login:          (email, password) =>
    api.post("/api/auth/login/", { email, password }),

  me:             ()                =>
    api.get("/api/auth/me/"),

  changePassword: (data)            =>
    api.post("/api/auth/change-password/", data),

  refresh:        (refresh)         =>
    api.post("/api/auth/token/refresh/", { refresh }),
};

export const schoolAPI = {
  me:    ()     => api.get("/api/school/me/"),
  list:  ()     => api.get("/api/schools/"),
  get:   (id)   => api.get(`/api/schools/${id}/`),
  create:(data) => api.post("/api/schools/", data),
  update:(id, data) => api.put(`/api/schools/${id}/`, data),
};

export default api;