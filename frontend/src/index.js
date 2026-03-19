/**
 * src/index.js
 *
 * Application entry point.
 *
 * Import order matters:
 *   1. variables.css  — CSS custom properties (fallback values)
 *   2. global.css     — reset + base component styles
 *   3. App            — component tree (wrapped in ThemeProvider)
 *
 * ThemeProvider will overwrite the :root variables at runtime
 * with per-school values from /api/school/me/.
 */

import React from "react";
import ReactDOM from "react-dom/client";

// ── Global styles (order is intentional) ─────────────────────────────────────
import "./styles/variables.css";
import "./styles/global.css";

import App from "./App";

const root = ReactDOM.createRoot(document.getElementById("root"));

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);