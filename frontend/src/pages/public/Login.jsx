/**
 * pages/public/Login.jsx
 *
 * School-branded login page.
 * Branding (logo, name, colours) comes from useTheme() — CSS vars handle colours.
 */

import React, { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTheme } from "../../context/ThemeContext";
import { useAuth } from "../../hooks/useAuth";
import { ROLE_DASHBOARDS } from "../../utils/roles";
import "./Login.css";

// ── Eye icon SVGs ──────────────────────────────────────────────────────────

const EyeOpen = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
);

const EyeClosed = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
);

// ── Component ──────────────────────────────────────────────────────────────

export default function Login() {
  const { school } = useTheme();
  const { login, isAuthenticated, isLoading, user, error, clearError } = useAuth();
  const navigate   = useNavigate();
  const location   = useLocation();
  const emailRef   = useRef(null);

  const [email,       setEmail]       = useState("");
  const [password,    setPassword]    = useState("");
  const [showPass,    setShowPass]    = useState(false);
  const [submitting,  setSubmitting]  = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});

  // Focus email on mount
  useEffect(() => { emailRef.current?.focus(); }, []);

  // Clear API error when user starts typing
  useEffect(() => {
    if (error) clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email, password]);

  // Already authenticated — redirect to dashboard
  useEffect(() => {
    if (isAuthenticated && user && !isLoading) {
      const intended = location.state?.from;
      const dest     = intended || ROLE_DASHBOARDS[user.role] || "/";
      navigate(dest, { replace: true });
    }
  }, [isAuthenticated, isLoading, user, navigate, location]);

  // ── Validation ────────────────────────────────────────────────────────────

  function validate() {
    const errs = {};
    if (!email.trim())       errs.email    = "Email address is required.";
    else if (!/\S+@\S+\.\S+/.test(email)) errs.email = "Enter a valid email.";
    if (!password)           errs.password = "Password is required.";
    return errs;
  }

  // ── Submit ─────────────────────────────────────────────────────────────────

  async function handleSubmit(e) {
    e.preventDefault();

    const errs = validate();
    if (Object.keys(errs).length) {
      setFieldErrors(errs);
      return;
    }
    setFieldErrors({});
    setSubmitting(true);

    await login(email.trim().toLowerCase(), password);
    // Navigation is handled inside AuthContext.login()
    setSubmitting(false);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const schoolName = school?.name || "School Portal";
  const logoUrl    = school?.logo || null;
  const motto      = school?.motto || null;

  return (
    <div className="login-root">
      {/* Background decorative blobs */}
      <div className="login-bg-blob login-bg-blob--1" aria-hidden="true" />
      <div className="login-bg-blob login-bg-blob--2" aria-hidden="true" />

      <main className="login-card" role="main">

        {/* ── Branding ── */}
        <header className="login-header">
          <div className="login-logo-wrap">
            {logoUrl
              ? <img src={logoUrl} alt={`${schoolName} logo`} className="login-logo" />
              : <div className="login-logo-fallback" aria-hidden="true">🏫</div>
            }
          </div>
          <h1 className="login-school-name">{schoolName}</h1>
          {motto && <p className="login-motto">"{motto}"</p>}
        </header>

        <div className="login-divider" aria-hidden="true" />

        <h2 className="login-title">Sign In</h2>
        <p className="login-subtitle">Enter your credentials to access your portal</p>

        {/* ── API error banner ── */}
        {error && (
          <div className="login-error-banner" role="alert">
            <span className="login-error-icon" aria-hidden="true">⚠</span>
            <span>{error}</span>
          </div>
        )}

        {/* ── Form ── */}
        <form className="login-form" onSubmit={handleSubmit} noValidate>

          <div className="login-field">
            <label htmlFor="login-email">Email Address</label>
            <input
              id="login-email"
              ref={emailRef}
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@school.edu.ng"
              className={fieldErrors.email ? "input--error" : ""}
              disabled={submitting}
              aria-describedby={fieldErrors.email ? "email-err" : undefined}
            />
            {fieldErrors.email && (
              <span id="email-err" className="field-error" role="alert">
                {fieldErrors.email}
              </span>
            )}
          </div>

          <div className="login-field">
            <label htmlFor="login-password">Password</label>
            <div className="login-password-wrap">
              <input
                id="login-password"
                type={showPass ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter your password"
                className={fieldErrors.password ? "input--error" : ""}
                disabled={submitting}
                aria-describedby={fieldErrors.password ? "pw-err" : undefined}
              />
              <button
                type="button"
                className="login-eye-btn"
                onClick={() => setShowPass(s => !s)}
                aria-label={showPass ? "Hide password" : "Show password"}
                tabIndex={-1}
              >
                {showPass ? <EyeClosed /> : <EyeOpen />}
              </button>
            </div>
            {fieldErrors.password && (
              <span id="pw-err" className="field-error" role="alert">
                {fieldErrors.password}
              </span>
            )}
          </div>

          <button
            type="submit"
            className="login-submit-btn"
            disabled={submitting}
          >
            {submitting
              ? <span className="login-btn-spinner" aria-hidden="true" />
              : null
            }
            {submitting ? "Signing in…" : "Sign In"}
          </button>

        </form>

        <footer className="login-footer">
          <p>Forgot your password? Contact your school administrator.</p>
        </footer>

      </main>
    </div>
  );
}