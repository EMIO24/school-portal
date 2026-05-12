import React, { useState, useEffect } from "react";
import api from "../../services/api";
import "./NotificationTemplates.css";

const EMPTY = { name: "", type: "sms", category: "general", subject: "", body: "" };

export default function NotificationTemplates() {
  const [templates, setTemplates] = useState([]);
  const [modal, setModal]         = useState(false);
  const [editing, setEditing]     = useState(null);
  const [form, setForm]           = useState(EMPTY);
  const [saving, setSaving]       = useState(false);

  useEffect(() => { load(); }, []);

  function load() {
    api.get("/api/notifications/templates/")
      .then(({ data: d }) => setTemplates(Array.isArray(d) ? d : d.results || []))
      .catch(() => {});
  }

  function openNew() { setEditing(null); setForm(EMPTY); setModal(true); }

  function openEdit(t) {
    setEditing(t.id);
    setForm({ name: t.name, type: t.type, category: t.category, subject: t.subject, body: t.body });
    setModal(true);
  }

  async function save() {
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/api/notifications/templates/${editing}/`, form);
      } else {
        await api.post("/api/notifications/templates/", form);
      }
      setModal(false);
      load();
    } catch {
      alert("Failed to save template. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function del(id) {
    if (!window.confirm("Delete this template?")) return;
    try {
      await api.delete(`/api/notifications/templates/${id}/`);
      load();
    } catch {
      alert("Failed to delete template.");
    }
  }

  return (
    <main className="page-shell">
      <div className="page-header-row">
        <h1 className="page-title">Notification Templates</h1>
        <button className="btn-primary" onClick={openNew}>+ New Template</button>
      </div>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Category</th>
              <th>Body Preview</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {templates.length === 0 && (
              <tr><td colSpan={5} className="empty-row">No templates yet.</td></tr>
            )}
            {templates.map(t => (
              <tr key={t.id}>
                <td>{t.name}</td>
                <td><span className={`type-badge type-${t.type}`}>{t.type.toUpperCase()}</span></td>
                <td className="capitalize">{t.category}</td>
                <td className="body-preview">{t.body?.slice(0, 80)}{t.body?.length > 80 ? "…" : ""}</td>
                <td className="action-cell">
                  <button className="btn-sm" onClick={() => openEdit(t)}>Edit</button>
                  <button className="btn-sm btn-danger" onClick={() => del(t.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h2>{editing ? "Edit Template" : "New Template"}</h2>

            <label>Name</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />

            <div className="form-row">
              <div>
                <label>Type</label>
                <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
                  <option value="sms">SMS</option>
                  <option value="email">Email</option>
                  <option value="both">Both</option>
                </select>
              </div>
              <div>
                <label>Category</label>
                <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                  {["result", "fee", "attendance", "exam", "general"].map(c => (
                    <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>

            {(form.type === "email" || form.type === "both") && (
              <>
                <label>Subject</label>
                <input value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} placeholder="Email subject" />
              </>
            )}

            <label>Body <span className="hint">(use {"{student_name}"}, {"{school_name}"}, {"{class_name}"})</span></label>
            <textarea
              rows={5}
              value={form.body}
              onChange={e => setForm({ ...form, body: e.target.value })}
              placeholder="Dear {student_name}, …"
            />

            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setModal(false)}>Cancel</button>
              <button className="btn-primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
