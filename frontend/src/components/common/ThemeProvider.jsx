/**
 * components/common/ThemeProvider.jsx
 *
 * Wraps the app in ThemeContext and gates rendering behind:
 *   - LoadingScreen while the API call is in-flight (and no cache exists)
 *   - BrandedErrorScreen if the API call fails and there is no cached theme
 *
 * If a cached theme exists, children render immediately using cached values
 * while the fresh fetch happens silently in the background.
 */

import React from "react";
import { ThemeProvider as ThemeContextProvider, useTheme } from "../../context/ThemeContext";
import LoadingScreen from "./LoadingScreen";
import "./ThemeProvider.css";

// ── Inner consumer — has access to ThemeContext ───────────────────────────────

function ThemeGate({ children }) {
  const { school, loading, error, refetch } = useTheme();

  // Show full-page loader only on first load with no cached data
  if (loading && !school) {
    return <LoadingScreen />;
  }

  // Show branded error only when fetch failed AND there's nothing cached
  if (error && !school) {
    return <BrandedErrorScreen error={error} onRetry={refetch} />;
  }

  return <>{children}</>;
}

// ── Branded error screen ──────────────────────────────────────────────────────

function BrandedErrorScreen({ error, onRetry }) {
  return (
    <div className="theme-error-screen">
      <div className="theme-error-card">
        <div className="theme-error-icon" aria-hidden="true">⚠</div>
        <h1 className="theme-error-title">School Not Found</h1>
        <p className="theme-error-message">
          {error || "Unable to load school configuration. Please check the URL."}
        </p>
        <button className="theme-error-retry" onClick={onRetry}>
          Try Again
        </button>
        <p className="theme-error-support">
          If this persists, contact{" "}
          <a href="mailto:support@myplatform.com">support@myplatform.com</a>
        </p>
      </div>
    </div>
  );
}

// ── Exported ThemeProvider ────────────────────────────────────────────────────

/**
 * Wrap your entire app:
 *
 *   <ThemeProvider>
 *     <App />
 *   </ThemeProvider>
 */
export default function ThemeProvider({ children }) {
  return (
    <ThemeContextProvider>
      <ThemeGate>{children}</ThemeGate>
    </ThemeContextProvider>
  );
}