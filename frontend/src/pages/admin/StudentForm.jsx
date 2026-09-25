import {referenceOptions} from '../../services/referenceOptions';
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../../services/api";
import "./StaffForm.css";

const initialForm = {
  new_first_name: "", new_last_name: "", new_email: "", dob: "", gender: "",
  current_class: "", state_of_origin: "", religion: "", guardian_name: "",
  guardian_phone: "", guardian_email: "", guardian_relationship: "guardian", status: "active",
};

export default function StudentForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [originalStatus,setOriginalStatus] = useState("active");
  const [form, setForm] = useState(initialForm);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true); setLoadError("");
    Promise.all([referenceOptions("/api/class-arms/"), id ? api.get(`/api/students/${id}/`) : Promise.resolve(null)])
      .then(([arms, student]) => {
        if (!active) return;
        setClasses(Array.isArray(arms.data) ? arms.data : arms.data.results || []);
        const data = student?.data;
        setOriginalStatus(data?.status || "active");
        setForm(data ? { ...initialForm, ...Object.fromEntries(Object.keys(initialForm).map(key => [key, data[key] ?? initialForm[key]])),
          new_first_name: data.first_name || "", new_last_name: data.last_name || "", new_email: data.email || "" } : initialForm);
      })
      .catch(() => { if (active) setLoadError("Could not load the student form. Reload this page to retry."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  async function submit(event) {
    event.preventDefault();
    if (id && form.status !== originalStatus && form.status !== "active" && !window.confirm("Deactivate this student account? Login will be disabled; academic and payment history will remain.")) return;
    setSaving(true); setErrors({}); setError("");
    const payload = { ...form, dob: form.dob || null, current_class: form.current_class ? Number(form.current_class) : null };

    try {
      const { data } = id ? await api.patch(`/api/students/${id}/`, payload) : await api.post("/api/students/", payload);
      navigate(`/admin/students/${data.id}`, { replace: true });
    } catch (err) {
      const details = err.response?.data;
      setErrors(details && typeof details === "object" ? details : {});
      setError(typeof details?.detail === "string" ? details.detail : "Could not save the student. Check the fields and try again.");
    } finally { setSaving(false); }
  }

  function field(key, label, type = "text", options = null) {
    const account = key.startsWith("new_");
    const props = { id: key, name: key, value: form[key], disabled: saving,
      required: account && key !== "new_email" && !id, onChange: e => setForm(prev => ({ ...prev, [key]: e.target.value })),
      "aria-invalid": Boolean(errors[key]), "aria-describedby": errors[key] ? `${key}-error` : undefined };
    return <div className="stf-field" key={key}>
      <label htmlFor={key}>{label}</label>
      {options ? <select {...props}>{options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select> : <input {...props} type={type} />}
      {errors[key] && <span className="field-error" id={`${key}-error`}>{Array.isArray(errors[key]) ? errors[key].join(" ") : String(errors[key])}</span>}
    </div>;
  }

  return <main className="stf-root">
    <h1>{id ? "Edit Student" : "Add Student"}</h1>
    {loading ? <p role="status">Loading student form...</p> : loadError ? <p role="alert">{loadError}</p> : <form className="stf-form" onSubmit={submit}>
      {error && <div role="alert" className="stf-api-error">{error}</div>}
      <section className="stf-section"><h2>Student details</h2>
        <p>{id ? "Changing a name or email changes future sign-in details. Admission number and history remain unchanged." : "The admission number is generated when you save. It is also the student's initial password."}</p>
        <div className="stf-grid stf-grid--3">
          {field("new_first_name", "First name")}{field("new_last_name", "Last name")}{field("new_email", "Email (optional)", "email")}
          {field("dob", "Date of birth", "date")}
          {field("gender", "Gender", "text", [["", "Select gender"], ["male", "Male"], ["female", "Female"]])}
          {field("current_class", "Class", "text", [["", "No class assigned"], ...classes.map(arm => [arm.id, arm.full_name || arm.name])])}
          {field("state_of_origin", "State of origin")}{field("religion", "Religion")}
          {id && field("status", "Status", "text", ["active", "graduated", "withdrawn", "suspended"].map(value => [value, value]))}
        </div>
      </section>
      <section className="stf-section"><h2>Guardian details</h2><div className="stf-grid stf-grid--3">
        {field("guardian_name", "Guardian name")}{field("guardian_phone", "Guardian phone", "tel")}{field("guardian_email", "Guardian email", "email")}
        {field("guardian_relationship", "Relationship", "text", ["father", "mother", "guardian", "sibling", "other"].map(value => [value, value]))}
      </div></section>
      <div className="stf-form-actions"><Link to="/admin/students">Cancel</Link><button className="btn btn-primary" disabled={saving} type="submit">{saving ? "Saving..." : id ? "Save Changes" : "Add Student"}</button></div>
    </form>}
  </main>;
}