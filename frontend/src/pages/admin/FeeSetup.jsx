import React, { useState, useEffect } from "react";
import api from "../../services/api";
import "./FeeSetup.css";

const EMPTY_CAT = { name: "", description: "", is_compulsory: true };

export default function FeeSetup() {
  const [terms, setTerms]               = useState([]);
  const [levels, setLevels]             = useState([]);
  const [categories, setCategories]     = useState([]);
  const [schedules, setSchedules]       = useState([]);
  const [selectedTerm, setSelectedTerm] = useState("");
  const [catModal, setCatModal]         = useState(false);
  const [editCat, setEditCat]           = useState(null);
  const [catForm, setCatForm]           = useState(EMPTY_CAT);
  const [grid, setGrid]                 = useState({});
  const [saving, setSaving]             = useState(false);
  const [toast, setToast]               = useState(null);

  useEffect(() => {
    api.get("/api/academics/terms/").then(({ data: d }) => {
      const list = Array.isArray(d) ? d : d.results || [];
      setTerms(list);
      const cur = list.find(t => t.is_current);
      if (cur) setSelectedTerm(String(cur.id));
    }).catch(() => {});

    api.get("/api/enrollment/class-levels/").then(({ data: d }) => {
      setLevels(Array.isArray(d) ? d : d.results || []);
    }).catch(() => {});

    loadCategories();
  }, []);

  useEffect(() => {
    if (selectedTerm) loadSchedules();
  }, [selectedTerm]);

  function loadCategories() {
    api.get("/api/fees/categories/").then(({ data: d }) => {
      setCategories(Array.isArray(d) ? d : d.results || []);
    }).catch(() => {});
  }

  function loadSchedules() {
    api.get(`/api/fees/schedule/?term=${selectedTerm}`).then(({ data: d }) => {
      const list = Array.isArray(d) ? d : d.results || [];
      setSchedules(list);
      const g = {};
      list.forEach(s => { g[`${s.class_level}_${s.fee_category}`] = s.amount; });
      setGrid(g);
    }).catch(() => {});
  }

  function openNewCat() { setEditCat(null); setCatForm(EMPTY_CAT); setCatModal(true); }
  function openEditCat(c) { setEditCat(c.id); setCatForm({ name: c.name, description: c.description, is_compulsory: c.is_compulsory }); setCatModal(true); }

  async function saveCat() {
    try {
      if (editCat) {
        await api.put(`/api/fees/categories/${editCat}/`, catForm);
      } else {
        await api.post("/api/fees/categories/", catForm);
      }
      setCatModal(false);
      loadCategories();
    } catch {
      alert("Failed to save category. Please try again.");
    }
  }

  async function deleteCat(id) {
    if (!window.confirm("Delete category? Existing schedules will be removed.")) return;
    try {
      await api.delete(`/api/fees/categories/${id}/`);
      loadCategories();
    } catch {
      alert("Failed to delete category.");
    }
  }

  function setAmount(levelId, catId, val) {
    setGrid(g => ({ ...g, [`${levelId}_${catId}`]: val }));
  }

  async function saveSchedule() {
    if (!selectedTerm) return;
    setSaving(true);
    const scheduleItems = [];
    levels.forEach(lv => {
      categories.forEach(cat => {
        const amt = grid[`${lv.id}_${cat.id}`];
        if (amt && Number(amt) > 0) {
          scheduleItems.push({ class_level_id: lv.id, fee_category_id: cat.id, amount: amt });
        }
      });
    });
    try {
      await api.post("/api/fees/schedule/", {
        term_id: Number(selectedTerm), schedules: scheduleItems,
      });
      setToast("Fee schedule saved.");
      setTimeout(() => setToast(null), 3000);
    } catch {
      alert("Failed to save fee schedule. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const selectedTermLabel = terms.find(t => String(t.id) === selectedTerm)?.name || "";

  return (
    <main className="page-shell fee-setup">
      <h1 className="page-title">Fee Setup</h1>
      {toast && <div className="fee-toast">{toast}</div>}

      <div className="fee-setup-layout">
        {/* Categories */}
        <section className="card fee-categories">
          <div className="section-header-row">
            <h2>Fee Categories</h2>
            <button className="btn-sm btn-primary" onClick={openNewCat}>+ Add</button>
          </div>
          <table>
            <thead><tr><th>Name</th><th>Compulsory</th><th></th></tr></thead>
            <tbody>
              {categories.map(c => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.is_compulsory ? "Yes" : "No"}</td>
                  <td className="action-cell">
                    <button className="btn-xs" onClick={() => openEditCat(c)}>Edit</button>
                    <button className="btn-xs btn-danger" onClick={() => deleteCat(c.id)}>Del</button>
                  </td>
                </tr>
              ))}
              {categories.length === 0 && <tr><td colSpan={3} className="empty-row">No categories yet.</td></tr>}
            </tbody>
          </table>
        </section>

        {/* Schedule grid */}
        <section className="card fee-grid-section">
          <div className="section-header-row">
            <h2>Fee Schedule</h2>
            <select className="fee-select" value={selectedTerm} onChange={e => setSelectedTerm(e.target.value)}>
              <option value="">— Select term —</option>
              {terms.map(t => <option key={t.id} value={t.id}>{t.name} {t.is_current ? "(current)" : ""}</option>)}
            </select>
            <button className="btn-primary btn-sm" onClick={saveSchedule} disabled={saving || !selectedTerm}>
              {saving ? "Saving…" : "Save Schedule"}
            </button>
          </div>
          {categories.length === 0 || levels.length === 0 ? (
            <p className="empty-row">Add fee categories and ensure class levels exist first.</p>
          ) : (
            <div className="table-scroll">
              <table className="schedule-grid">
                <thead>
                  <tr>
                    <th>Class</th>
                    {categories.map(c => <th key={c.id}>{c.name}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {levels.map(lv => (
                    <tr key={lv.id}>
                      <td className="level-name">{lv.name}</td>
                      {categories.map(cat => (
                        <td key={cat.id}>
                          <input
                            type="number"
                            className="amount-input"
                            placeholder="0"
                            value={grid[`${lv.id}_${cat.id}`] || ""}
                            onChange={e => setAmount(lv.id, cat.id, e.target.value)}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {catModal && (
        <div className="modal-overlay" onClick={() => setCatModal(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h2>{editCat ? "Edit Category" : "New Category"}</h2>
            <label>Name</label>
            <input value={catForm.name} onChange={e => setCatForm({ ...catForm, name: e.target.value })} />
            <label>Description</label>
            <input value={catForm.description} onChange={e => setCatForm({ ...catForm, description: e.target.value })} />
            <label className="checkbox-label">
              <input type="checkbox" checked={catForm.is_compulsory} onChange={e => setCatForm({ ...catForm, is_compulsory: e.target.checked })} />
              Compulsory
            </label>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setCatModal(false)}>Cancel</button>
              <button className="btn-primary" onClick={saveCat}>Save</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
