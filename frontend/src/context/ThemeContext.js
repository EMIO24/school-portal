/**
 * context/ThemeContext.js
 *
 * Fetches school branding from GET /api/school/me/ and writes CSS variables
 * to document.documentElement so every component can use var(--color-primary) etc.
 *
 * Load order:
 *   1. Instantly apply cached theme from localStorage (no flash of unstyled content)
 *   2. Fetch fresh theme from API in background
 *   3. Update CSS variables + refresh cache
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

// ── Constants ─────────────────────────────────────────────────────────────────

const CACHE_KEY = "school_theme";
const API_URL = process.env.REACT_APP_API_URL || "";

/** Default fallback theme — matches variables.css :root defaults */
const DEFAULT_THEME = {
  name: "",
  logo: "",
  subdomain: "",
  motto: "",
  theme: {
    primary_color: "#1B3A6B",
    secondary_color: "#2E5DA8",
    accent_color: "#E07B00",
    font_family: "'Segoe UI', sans-serif",
  },
};

// ── CSS variable injection ────────────────────────────────────────────────────

/**
 * Write school theme values as CSS custom properties on :root.
 * Called once on cache load and again after API fetch.
 *
 * @param {object} schoolData  — response from /api/school/me/
 */
function applyThemeToDom(schoolData) {
  const root = document.documentElement;
  const t = schoolData?.theme || {};

  root.style.setProperty("--color-primary", t.primary_color || DEFAULT_THEME.theme.primary_color);
  root.style.setProperty("--color-secondary", t.secondary_color || DEFAULT_THEME.theme.secondary_color);
  root.style.setProperty("--color-accent", t.accent_color || DEFAULT_THEME.theme.accent_color);
  root.style.setProperty("--font-main", t.font_family || DEFAULT_THEME.theme.font_family);
  root.style.setProperty("--school-name", `"${schoolData?.name || ""}"`);
  root.style.setProperty("--school-logo", schoolData?.logo ? `url("${schoolData.logo}")` : "none");
}

// ── Context ───────────────────────────────────────────────────────────────────

export const ThemeContext = createContext(null);

/**
 * useTheme — consume the ThemeContext.
 * Must be used inside <ThemeProvider>.
 */
export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used inside <ThemeProvider>");
  }
  return ctx;
}

// ── Provider ──────────────────────────────────────────────────────────────────

/**
 * ThemeProvider
 *
 * Wrap your entire app with this. It:
 *   - Applies cached theme instantly (avoids flash)
 *   - Fetches /api/school/me/ and refreshes
 *   - Exposes { school, loading, error, refetch } via context
 */
export function ThemeProvider({ children }) {
  const [school, setSchool] = useState(() => {
    // Hydrate from localStorage synchronously so CSS vars are set before paint
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        applyThemeToDom(parsed);
        return parsed;
      }
    } catch {
      // Corrupt cache — ignore and fetch fresh
    }
    return null;
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTheme = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/school/me/`, {
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status} — school not found for this subdomain.`);
      }

      const data = await res.json();

      // Apply to DOM immediately
      applyThemeToDom(data);

      // Persist to localStorage for next load
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify(data));
      } catch {
        // Storage full or blocked — non-fatal
      }

      setSchool(data);
    } catch (err) {
      setError(err.message || "Failed to load school configuration.");
      // Keep any cached data in state so UI can still render partially
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTheme();
  }, [fetchTheme]);

  return (
    <ThemeContext.Provider
      value={{
        school,               // full school object from API
        loading,              // true while fetching
        error,                // string | null
        refetch: fetchTheme,  // call to manually reload theme
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}