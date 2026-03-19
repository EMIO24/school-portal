/**
 * pages/public/ChangePassword.jsx
 *
 * Forced password change page — shown after first login
 * when must_change_password === true.
 *
 * On success: redirects to the user's role dashboard.
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { authAPI } from "../../services/api";
import { useAuth } from "../../hooks/useAuth";
import { useTheme } from "../../context/ThemeContext";
import { ROLE_DASHBOARDS } from "../../utils/roles";
import "./ChangePassword.css";

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

function PasswordField({ id, label, value, onChange, show, onToggle, error, disabled, autoComplete }) {
  return (
    <div className="cpw-field">
      <label htmlFor={id}>{label}</label>
      <div className="cpw-pw-wrap">
        <input
          id={id}
          type={show ? "text" : "password"}
          value={value}
          onChange={onChange}
          autoComplete={autoComplete}
          className={error ? "input--error" : ""}
          disabled={disabled}
        />
        <button type="button" className="cpw-eye-btn" onClick={onToggle}
          aria-label={show ? "Hide" : "Show"} tabIndex={-1}>
          {show ? <EyeClosed /> : <EyeOpen />}
        </button>
      </div>
      {error && <span className="field-error" role="alert">{error}</span>}
    </div>
  );
}

export default function ChangePassword() {
  const { user, updateUser } = useAuth();
  const { school }           = useTheme();
  const navigate             = useNavigate();

  const [current,     setCurrent]     = useState("");
  const [newPw,       setNewPw]       = useState("");
  const [confirm,     setConfirm]     = useState("");
  const [show,        setShow]        = useState({ current: false, new: false, confirm: false });
  const [errors,      setErrors]      = useState({});
  const [apiError,    setApiError]    = useState(null);
  const [submitting,  setSubmitting]  = useState(false);
  const [success,     setSuccess]     = useState(false);

  function toggleShow(field) {
    setShow(s => ({ ...s, [field]: !s[field] }));
  }

  function validate() {
    const errs = {};
    if (!current)       errs.current = "Current password is required.";
    if (!newPw)         errs.newPw   = "New password is required.";
    else if (newPw.length < 8) errs.newPw = "Password must be at least 8 characters.";
    if (newPw !== confirm) errs.confirm = "Passwords do not match.";
    if (current && newPw && current === newPw)
      errs.newPw = "New password must be different from current password.";
    return errs;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }

    setErrors({});
    setApiError(null);
    setSubmitting(true);

    try {
      await authAPI.changePassword({
        current_password: current,
        new_password:     newPw,
        confirm_password: confirm,
      });

      setSuccess(true);
      updateUser({ mustChangePassword: false });

      setTimeout(() => {
        navigate(ROLE_DASHBOARDS[user?.role] || "/", { replace: true });
      }, 1800);
    } catch (err) {
      const data = err.response?.data;
      setApiError(
        data?.current_password?.[0] ||
        data?.new_password?.[0] ||
        data?.detail ||
        "Failed to change password. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  // ── Password strength indicator ────────────────────────────────────────

  function strength(pw) {
    if (!pw) return 0;
    let score = 0;
    if (pw.length >= 8)  score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    return score; // 0–5
  }

  const str      = strength(newPw);
  const strLabel = ["", "Very weak", "Weak", "Fair", "Strong", "Very strong"][str];
  const strClass = ["", "str-1", "str-2", "str-3", "str-4", "str-5"][str];

  return (
    <div className="cpw-root">
      <div className="cpw-bg-blob cpw-bg-blob--1" aria-hidden="true" />
      <div className="cpw-bg-blob cpw-bg-blob--2" aria-hidden="true" />

      <main className="cpw-card">
        {/* Branding */}
        <header className="cpw-header">
          {school?.logo
            ? <img src={school.logo} alt={school.name} className="cpw-logo" />
            : <div className="cpw-logo-fallback" aria-hidden="true">🔐</div>
          }
          <h1 className="cpw-school-name">{school?.name || "School Portal"}</h1>
        </header>

        <div className="cpw-divider" aria-hidden="true" />

        {success ? (
          <div className="cpw-success">
            <div className="cpw-success-icon" aria-hidden="true">✓</div>
            <h2>Password Changed!</h2>
            <p>Redirecting you to your dashboard…</p>
          </div>
        ) : (
          <>
            <h2 className="cpw-title">Set New Password</h2>
            <p className="cpw-subtitle">
              {user?.mustChangePassword
                ? "You must set a new password before continuing."
                : "Update your account password below."}
            </p>

            {apiError && (
              <div className="cpw-error-banner" role="alert">
                <span aria-hidden="true">⚠</span> {apiError}
              </div>
            )}

            <form className="cpw-form" onSubmit={handleSubmit} noValidate>
              <PasswordField
                id="cpw-current" label="Current Password"
                value={current} onChange={e => setCurrent(e.target.value)}
                show={show.current} onToggle={() => toggleShow("current")}
                error={errors.current} disabled={submitting}
                autoComplete="current-password"
              />

              <PasswordField
                id="cpw-new" label="New Password"
                value={newPw} onChange={e => setNewPw(e.target.value)}
                show={show.new} onToggle={() => toggleShow("new")}
                error={errors.newPw} disabled={submitting}
                autoComplete="new-password"
              />

              {/* Strength meter */}
              {newPw && (
                <div className="cpw-strength">
                  <div className="cpw-strength-bars">
                    {[1,2,3,4,5].map(i => (
                      <div
                        key={i}
                        className={`cpw-strength-bar ${i <= str ? strClass : ""}`}
                      />
                    ))}
                  </div>
                  <span className={`cpw-strength-label ${strClass}`}>{strLabel}</span>
                </div>
              )}

              <PasswordField
                id="cpw-confirm" label="Confirm New Password"
                value={confirm} onChange={e => setConfirm(e.target.value)}
                show={show.confirm} onToggle={() => toggleShow("confirm")}
                error={errors.confirm} disabled={submitting}
                autoComplete="new-password"
              />

              <button type="submit" className="cpw-submit-btn" disabled={submitting}>
                {submitting && <span className="cpw-btn-spinner" aria-hidden="true" />}
                {submitting ? "Saving…" : "Change Password"}
              </button>
            </form>
          </>
        )}
      </main>
    </div>
  );
}