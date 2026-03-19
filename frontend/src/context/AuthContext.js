/**
 * context/AuthContext.js
 *
 * Manages authentication state for the entire app.
 *
 * State shape:
 *   user            — { id, email, firstName, lastName, fullName, role,
 *                       photo, mustChangePassword, school }
 *   accessToken     — in-memory only (never localStorage)
 *   isAuthenticated — boolean
 *   isLoading       — true while loadUser() runs on mount
 *
 * Persisted across page reloads via:
 *   - refresh_token in localStorage
 *   - loadUser() calls /api/auth/me/ using the refresh → new access token
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
} from "react";
import { useNavigate } from "react-router-dom";
import { authAPI, tokenStore } from "../services/api";
import { ROLE_DASHBOARDS } from "../utils/roles";

// ── Context ────────────────────────────────────────────────────────────────

export const AuthContext = createContext(null);

// ── Reducer ────────────────────────────────────────────────────────────────

const initialState = {
  user:            null,
  isAuthenticated: false,
  isLoading:       true,   // true on mount until loadUser() resolves
  error:           null,
};

function authReducer(state, action) {
  switch (action.type) {
    case "AUTH_SUCCESS":
      return {
        ...state,
        user:            action.payload,
        isAuthenticated: true,
        isLoading:       false,
        error:           null,
      };
    case "AUTH_FAILED":
      return {
        ...state,
        user:            null,
        isAuthenticated: false,
        isLoading:       false,
        error:           action.payload || null,
      };
    case "AUTH_LOADING":
      return { ...state, isLoading: true, error: null };
    case "CLEAR_ERROR":
      return { ...state, error: null };
    default:
      return state;
  }
}

// ── User normaliser ────────────────────────────────────────────────────────

function normaliseUser(apiUser) {
  return {
    id:                 apiUser.id,
    email:              apiUser.email,
    firstName:          apiUser.first_name,
    lastName:           apiUser.last_name,
    fullName:           apiUser.full_name,
    role:               apiUser.role,
    photo:              apiUser.profile_photo || null,
    mustChangePassword: apiUser.must_change_password,
    school:             apiUser.school || null,
  };
}

// ── Provider ───────────────────────────────────────────────────────────────

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialState);
  const navigate = useNavigate();

  // ── Load user on mount (persisted session) ───────────────────────────────

  const loadUser = useCallback(async () => {
    const refresh = tokenStore.getRefresh();
    if (!refresh) {
      dispatch({ type: "AUTH_FAILED" });
      return;
    }

    dispatch({ type: "AUTH_LOADING" });
    try {
      // Exchange refresh token for new access token
      const { data: tokens } = await authAPI.refresh(refresh);
      tokenStore.setTokens(tokens);

      // Fetch user profile
      const { data: apiUser } = await authAPI.me();
      dispatch({ type: "AUTH_SUCCESS", payload: normaliseUser(apiUser) });
    } catch {
      tokenStore.clearAll();
      dispatch({ type: "AUTH_FAILED" });
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  // Listen for forced logout events (from api.js interceptor)
  useEffect(() => {
    const handleForcedLogout = () => {
      dispatch({ type: "AUTH_FAILED" });
      navigate("/login", { replace: true });
    };
    window.addEventListener("auth:logout", handleForcedLogout);
    return () => window.removeEventListener("auth:logout", handleForcedLogout);
  }, [navigate]);

  // ── login ────────────────────────────────────────────────────────────────

  const login = useCallback(async (email, password) => {
    dispatch({ type: "AUTH_LOADING" });
    try {
      const { data } = await authAPI.login(email, password);

      tokenStore.setTokens({ access: data.access, refresh: data.refresh });
      const user = normaliseUser(data.user);
      dispatch({ type: "AUTH_SUCCESS", payload: user });

      // ── Post-login routing ───────────────────────────────────────────────
      if (user.mustChangePassword) {
        navigate("/change-password", { replace: true });
      } else {
        navigate(ROLE_DASHBOARDS[user.role] || "/", { replace: true });
      }

      return { success: true };
    } catch (err) {
      const message =
        err.response?.data?.errors?.non_field_errors?.[0] ||
        err.response?.data?.errors?.detail ||
        err.response?.data?.detail ||
        "Login failed. Please check your credentials.";

      dispatch({ type: "AUTH_FAILED", payload: message });
      return { success: false, error: message };
    }
  }, [navigate]);

  // ── logout ───────────────────────────────────────────────────────────────

  const logout = useCallback(() => {
    tokenStore.clearAll();
    dispatch({ type: "AUTH_FAILED" });
    navigate("/login", { replace: true });
  }, [navigate]);

  // ── clearError ───────────────────────────────────────────────────────────

  const clearError = useCallback(() => {
    dispatch({ type: "CLEAR_ERROR" });
  }, []);

  // ── updateUser (after profile edit / password change) ───────────────────

  const updateUser = useCallback((partial) => {
    dispatch({
      type: "AUTH_SUCCESS",
      payload: { ...state.user, ...partial },
    });
  }, [state.user]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        logout,
        loadUser,
        clearError,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}