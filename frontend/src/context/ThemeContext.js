import { useLocation } from "react-router-dom";
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

import { API_BASE_URL as API_URL, TENANT_HEADERS } from "../services/config";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

// ── Constants ─────────────────────────────────────────────────────────────────

export const THEME_CACHE_KEY = "school_theme:" + (TENANT_HEADERS["X-School-Slug"] || window.location.hostname);
const CACHE_KEY = THEME_CACHE_KEY;


// When deployed to Vercel (different domain from Railway backend),
// the backend can't detect the school from the Host subdomain.
// Set REACT_APP_SCHOOL_SLUG so requests carry X-School-Slug header instead.
const SCHOOL_SLUG = TENANT_HEADERS["X-School-Slug"] || "";

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
export function applyThemeToDom(schoolData) {
  const root = document.documentElement;
  const t = schoolData?.theme || {};

  root.style.setProperty("--color-primary", t.primary_color || DEFAULT_THEME.theme.primary_color);
  root.style.setProperty("--color-secondary", t.secondary_color || DEFAULT_THEME.theme.secondary_color);
  root.style.setProperty("--color-accent", t.accent_color || DEFAULT_THEME.theme.accent_color);
  root.style.setProperty("--font-main", t.font_family || DEFAULT_THEME.theme.font_family);
  // Older modules used shorter token names. Keep all screens on the same palette.
  const primary = t.primary_color || DEFAULT_THEME.theme.primary_color;
  const secondary = t.secondary_color || DEFAULT_THEME.theme.secondary_color;
  const accent = t.accent_color || DEFAULT_THEME.theme.accent_color;
  const contrast = hex => {
    const rgb = hex.replace('#', '').match(/../g).map(v => parseInt(v,16)/255).map(v => v <= .04045 ? v/12.92 : ((v+.055)/1.055)**2.4);
    const luminance = rgb[0]*.2126 + rgb[1]*.7152 + rgb[2]*.0722;
    return luminance > .179 ? '#10202B' : '#FFFFFF';
  };
  for (const [name,value] of Object.entries({primary, secondary, accent, 'on-primary':contrast(primary), 'on-accent':contrast(accent),
    'primary-light':'color-mix(in srgb, '+primary+' 10%, white)', 'primary-dark':'color-mix(in srgb, '+primary+' 80%, black)',
    'bg':'#F4F6FA', 'surface':'#FFFFFF', 'text':'#172B3A', 'text-muted':'#627381', 'border':'#DEE5EA'})) root.style.setProperty('--'+name,value);
  root.dataset.portalLayout = ['scholar','campus','studio','executive','heritage'].includes(t.layout) ? t.layout : 'scholar';

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
  const { pathname } = useLocation();
  const platform = pathname.startsWith("/platform/") || pathname.startsWith("/superadmin/") || pathname === "/register-school";
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
      const headers = { Accept: "application/json" };
      if (SCHOOL_SLUG) headers["X-School-Slug"] = SCHOOL_SLUG;

      const res = await fetch(`${API_URL}/api/school/me/`, { headers });

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
    if (platform) { applyThemeToDom(DEFAULT_THEME); document.documentElement.dataset.portalLayout = 'platform'; setLoading(false); }
    else fetchTheme();
  }, [fetchTheme, platform]);
  useEffect(() => {
    if (platform) { applyThemeToDom(DEFAULT_THEME); document.documentElement.dataset.portalLayout = 'platform'; }
    else if (school) applyThemeToDom(school);
  }, [school, platform]);


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