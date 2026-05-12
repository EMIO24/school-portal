import React, { useState, useEffect } from "react";
import api from "../../services/api";
import "./Notifications.css";

const VARIABLE_HINTS = ["{student_name}", "{school_name}", "{class_name}", "{admission_no}"];

const STATUS_LABEL = { sent: "Sent", failed: "Failed", pending: "Pending" };

export default function Notifications() {
  const [channel, setChannel]           = useState("sms");
  const [recipientType, setRecipientType] = useState("all_parents");
  const [classArmId, setClassArmId]     = useState("");
  const [classArms, setClassArms]       = useState([]);
  const [templates, setTemplates]       = useState([]);
  const [templateId, setTemplateId]     = useState("");
  const [customMessage, setCustomMessage] = useState("");
  const [subject, setSubject]           = useState("");
  const [logs, setLogs]                 = useState([]);
  const [sending, setSending]           = useState(false);
  const [toast, setToast]               = useState(null);

  useEffect(() => {
    api.get("/api/enrollment/class-arms/")
      .then(({ data: d }) => setClassArms(Array.isArray(d) ? d : d.results || []))
      .catch(() => {});
    api.get("/api/notifications/templates/")
      .then(({ data: d }) => setTemplates(Array.isArray(d) ? d : d.results || []))
      .catch(() => {});
    loadLogs();
  }, []);

  function loadLogs() {
    api.get("/api/notifications/logs/")
      .then(({ data: d }) => setLogs(Array.isArray(d) ? d : d.results || []))
      .catch(() => {});
  }

  const selectedTemplate = templates.find(t => String(t.id) === String(templateId));
  const messageBody = selectedTemplate ? selectedTemplate.body : customMessage;
  const charCount   = messageBody.length;

  async function handleSend() {
    setSending(true);
    const body = {
      channel,
      recipient_type: recipientType,
      ...(recipientType === "class" && classArmId ? { class_arm_id: Number(classArmId) } : {}),
      ...(templateId ? { template_id: Number(templateId) } : { message: customMessage, subject }),
    };
    try {
      const { data } = await api.post("/api/notifications/send/", body);
      setToast(`${data.sent} sent, ${data.failed} failed`);
      loadLogs();
    } catch {
      setToast("Network error");
    } finally {
      setSending(false);
      setTimeout(() => setToast(null), 4000);
    }
  }

  return (
    <main className="page-shell notif-page">
      <h1 className="page-title">Notifications</h1>
      {toast && <div className="notif-toast">{toast}</div>}

      <div className="notif-layout">
        {/* ── Compose ── */}
        <section className="notif-compose card">
          <h2>Compose</h2>

          <label className="field-label">Channel</label>
          <div className="notif-channel-group">
            {["sms", "email", "both"].map(c => (
              <label key={c} className={`channel-chip ${channel === c ? "active" : ""}`}>
                <input type="radio" value={c} checked={channel === c} onChange={() => setChannel(c)} />
                {c.toUpperCase()}
              </label>
            ))}
          </div>

          <label className="field-label">Recipients</label>
          <div className="notif-recipient-group">
            {[["all_parents", "All Parents"], ["class", "By Class"], ["individual", "Individual"]].map(([v, l]) => (
              <label key={v} className={`recipient-chip ${recipientType === v ? "active" : ""}`}>
                <input type="radio" value={v} checked={recipientType === v} onChange={() => setRecipientType(v)} />
                {l}
              </label>
            ))}
          </div>

          {recipientType === "class" && (
            <select className="notif-select" value={classArmId} onChange={e => setClassArmId(e.target.value)}>
              <option value="">— Select class —</option>
              {classArms.map(ca => (
                <option key={ca.id} value={ca.id}>{ca.full_name || ca.name}</option>
              ))}
            </select>
          )}

          <label className="field-label">Template</label>
          <select className="notif-select" value={templateId} onChange={e => setTemplateId(e.target.value)}>
            <option value="">— Custom message —</option>
            {templates.map(t => (
              <option key={t.id} value={t.id}>{t.name} ({t.type.toUpperCase()})</option>
            ))}
          </select>

          {!templateId && (
            <>
              {(channel === "email" || channel === "both") && (
                <input
                  className="notif-input"
                  placeholder="Email subject"
                  value={subject}
                  onChange={e => setSubject(e.target.value)}
                />
              )}
              <textarea
                className="notif-textarea"
                placeholder="Type your message…"
                value={customMessage}
                onChange={e => setCustomMessage(e.target.value)}
                rows={5}
              />
            </>
          )}

          {selectedTemplate && (
            <div className="notif-preview">
              <strong>Preview:</strong>
              <p>{selectedTemplate.body.replace(/\{student_name\}/g, "Amaka Obi").replace(/\{school_name\}/g, "Demo School")}</p>
            </div>
          )}

          {(channel === "sms" || channel === "both") && (
            <div className={`sms-counter ${charCount > 160 ? "over" : ""}`}>
              {charCount}/160 chars {charCount > 160 && `(${Math.ceil(charCount / 160)} SMS)`}
            </div>
          )}

          <div className="notif-hints">
            {VARIABLE_HINTS.map(v => <span key={v} className="var-chip">{v}</span>)}
          </div>

          <button className="btn-primary" onClick={handleSend} disabled={sending}>
            {sending ? "Sending…" : "Send"}
          </button>
        </section>

        {/* ── History ── */}
        <section className="notif-history card">
          <h2>Send History</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Channel</th>
                  <th>Recipient</th>
                  <th>Status</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 && (
                  <tr><td colSpan={5} className="empty-row">No messages sent yet.</td></tr>
                )}
                {logs.map(log => (
                  <tr key={log.id}>
                    <td>{log.sent_at ? new Date(log.sent_at).toLocaleString() : "—"}</td>
                    <td>{log.channel.toUpperCase()}</td>
                    <td>{log.recipient_phone || log.recipient_email || log.student_name || "—"}</td>
                    <td><span className={`status-badge status-${log.status}`}>{STATUS_LABEL[log.status]}</span></td>
                    <td className="msg-preview">{log.message_body?.slice(0, 80)}{log.message_body?.length > 80 ? "…" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
