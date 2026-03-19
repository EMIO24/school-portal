/**
 * components/common/LoadingScreen.jsx
 *
 * Full-page loading screen shown while ThemeProvider fetches /api/school/me/.
 *
 * Features:
 *   - Shows cached school logo if available in localStorage
 *   - Spinner uses var(--color-primary) so it works even with cached theme
 *   - School name fades in below the logo
 *   - Graceful fallback when no cache exists (generic platform logo)
 */

import React, { useEffect, useState } from "react";
import "./LoadingScreen.css";

const CACHE_KEY = "school_theme";

function getCachedTheme() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function LoadingScreen() {
  const [cached, setCached] = useState(null);

  useEffect(() => {
    setCached(getCachedTheme());
  }, []);

  const logoUrl = cached?.logo || null;
  const schoolName = cached?.name || "Loading…";

  return (
    <div className="ls-root" role="status" aria-label="Loading school portal">
      <div className="ls-card">
        {/* Logo or placeholder */}
        <div className="ls-logo-wrap">
          {logoUrl ? (
            <img
              className="ls-logo"
              src={logoUrl}
              alt={`${schoolName} logo`}
              draggable={false}
            />
          ) : (
            <div className="ls-logo-placeholder" aria-hidden="true">
              <span>🏫</span>
            </div>
          )}
        </div>

        {/* School name */}
        <p className="ls-name">{schoolName}</p>

        {/* Spinner */}
        <div className="ls-spinner" aria-hidden="true">
          <div className="ls-spinner-ring" />
        </div>

        <p className="ls-caption">Setting up your portal…</p>
      </div>
    </div>
  );
}