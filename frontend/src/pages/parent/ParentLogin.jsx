import React, { useState, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "../../context/AuthContext";
import { tokenStore } from "../../services/api";
import "./ParentLogin.css";

export default function ParentLogin() {
  const [mode, setMode]         = useState("otp");   // "otp" | "email"
  const [step, setStep]         = useState("phone"); // "phone" | "otp"
  const [phone, setPhone]       = useState("");
  const [otp, setOtp]           = useState("");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const navigate = useNavigate();
  const { loadUser } = useContext(AuthContext);

  async function requestOTP() {
    if (!phone) return;
    setLoading(true); setError("");
    try {
      const res  = await fetch("/api/auth/parent/otp-request/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      if (res.ok) {
        setStep("otp");
      } else {
        const d = await res.json();
        setError(d.error || "Could not send OTP.");
      }
    } catch { setError("Network error."); }
    finally { setLoading(false); }
  }

  async function verifyOTP() {
    if (!otp) return;
    setLoading(true); setError("");
    try {
      const res  = await fetch("/api/auth/parent/otp-verify/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, otp }),
      });
      const data = await res.json();
      if (res.ok) {
        tokenStore.setTokens({ access: data.access, refresh: data.refresh });
        await loadUser();
        navigate("/parent/dashboard");
      } else {
        setError(data.error || "Invalid OTP.");
      }
    } catch { setError("Network error."); }
    finally { setLoading(false); }
  }

  async function loginEmail() {
    setLoading(true); setError("");
    try {
      const res  = await fetch("/api/auth/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (res.ok && data.role === "parent") {
        tokenStore.setTokens({ access: data.access, refresh: data.refresh });
        await loadUser();
        navigate("/parent/dashboard");
      } else {
        setError(data.errors?.non_field_errors?.[0] || "Login failed.");
      }
    } catch { setError("Network error."); }
    finally { setLoading(false); }
  }

  return (
    <div className="parent-login-screen">
      <div className="parent-login-card">
        <div className="login-logo">🏫</div>
        <h1>Parent Portal</h1>
        <p className="login-subtitle">Stay connected with your child's school</p>

        <div className="mode-toggle">
          <button className={mode === "otp" ? "active" : ""} onClick={() => { setMode("otp"); setStep("phone"); setError(""); }}>
            Phone / OTP
          </button>
          <button className={mode === "email" ? "active" : ""} onClick={() => { setMode("email"); setError(""); }}>
            Email / Password
          </button>
        </div>

        {error && <p className="login-error">{error}</p>}

        {mode === "otp" && step === "phone" && (
          <>
            <label>Phone Number</label>
            <input
              type="tel"
              placeholder="080xxxxxxxx"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              onKeyDown={e => e.key === "Enter" && requestOTP()}
            />
            <button className="login-btn" onClick={requestOTP} disabled={loading || !phone}>
              {loading ? "Sending…" : "Send OTP"}
            </button>
          </>
        )}

        {mode === "otp" && step === "otp" && (
          <>
            <p className="otp-hint">Enter the 6-digit code sent to <strong>{phone}</strong></p>
            <input
              type="number"
              placeholder="123456"
              value={otp}
              onChange={e => setOtp(e.target.value)}
              maxLength={6}
              onKeyDown={e => e.key === "Enter" && verifyOTP()}
              className="otp-input"
            />
            <button className="login-btn" onClick={verifyOTP} disabled={loading || otp.length < 6}>
              {loading ? "Verifying…" : "Verify & Login"}
            </button>
            <button className="link-btn" onClick={() => setStep("phone")}>← Change number</button>
          </>
        )}

        {mode === "email" && (
          <>
            <label>Email</label>
            <input type="email" placeholder="parent@email.com" value={email} onChange={e => setEmail(e.target.value)} />
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} onKeyDown={e => e.key === "Enter" && loginEmail()} />
            <button className="login-btn" onClick={loginEmail} disabled={loading || !email || !password}>
              {loading ? "Logging in…" : "Login"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
