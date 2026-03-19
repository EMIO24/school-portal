/**
 * components/admin/BulkImport.jsx
 *
 * Drag-and-drop CSV importer for student enrollment.
 * Shows a preview table of parsed rows before upload.
 * After upload, shows a detailed per-row error report.
 */

import React, { useCallback, useRef, useState } from "react";
import api from "../../services/api";
import "./BulkImport.css";

const REQUIRED_COLS = [
  "first_name","last_name","email",
  "gender","dob","class_level",
  "guardian_name","guardian_phone",
];

const OPTIONAL_COLS = [
  "state_of_origin","religion",
  "guardian_email","guardian_relationship",
];

// ── CSV parser (client-side preview only) ─────────────────────────────────

function parseCSVPreview(text, maxRows = 5) {
  const lines   = text.trim().split(/\r?\n/);
  if (lines.length < 2) return { headers: [], rows: [], totalRows: 0 };

  const headers = lines[0].split(",").map(h => h.trim().replace(/^"|"$/g, ""));
  const rows    = lines.slice(1).map(line => {
    const vals = line.split(",").map(v => v.trim().replace(/^"|"$/g, ""));
    return headers.reduce((obj, h, i) => { obj[h] = vals[i] || ""; return obj; }, {});
  });

  return { headers, rows: rows.slice(0, maxRows), totalRows: rows.length };
}

// ── Sub-components ─────────────────────────────────────────────────────────

function DropZone({ onFile, dragging, onDragOver, onDragLeave, onDrop }) {
  const inputRef = useRef();
  return (
    <div
      className={`bi-dropzone ${dragging ? "bi-dropzone--over" : ""}`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === "Enter" && inputRef.current?.click()}
      aria-label="Upload CSV file"
    >
      <div className="bi-dz-icon">📄</div>
      <p className="bi-dz-title">Drag & drop your CSV file here</p>
      <p className="bi-dz-sub">or click to browse</p>
      <span className="bi-dz-badge">.csv files only</span>
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="bi-hidden-input"
        onChange={e => onFile(e.target.files[0])}
      />
    </div>
  );
}

function TemplateDownload() {
  function download() {
    const headers = [...REQUIRED_COLS, ...OPTIONAL_COLS].join(",");
    const example = "Amaka,Okonkwo,amaka@school.edu.ng,female,2008-05-14,JSS1,Mrs Okonkwo,08012345678,Lagos,Christianity,parent@example.com,mother";
    const blob = new Blob([headers + "\n" + example], { type: "text/csv" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "student_import_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <button className="btn btn-ghost btn-sm bi-template-btn" onClick={download} type="button">
      ↓ Download Template
    </button>
  );
}

function PreviewTable({ headers, rows, totalRows }) {
  const showing = rows.length;
  return (
    <div className="bi-preview">
      <div className="bi-preview-header">
        <span className="bi-preview-title">Preview</span>
        <span className="bi-preview-count">
          Showing {showing} of {totalRows} rows
        </span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {headers.map(h => (
                <th key={h} className={REQUIRED_COLS.includes(h) ? "bi-col-required" : ""}>
                  {h}
                  {REQUIRED_COLS.includes(h) && <span className="bi-req-dot" title="Required" />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {headers.map(h => (
                  <td key={h} className={!row[h] && REQUIRED_COLS.includes(h) ? "bi-cell-missing" : ""}>
                    {row[h] || <span className="text-muted">—</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalRows > showing && (
        <p className="bi-preview-more">… and {totalRows - showing} more rows</p>
      )}
    </div>
  );
}

function ResultPanel({ result, onReset }) {
  const hasErrors = result.errors?.length > 0;
  return (
    <div className="bi-result">
      <div className="bi-result-summary">
        <div className={`bi-result-stat bi-result-stat--success`}>
          <span className="bi-stat-num">{result.success_count}</span>
          <span className="bi-stat-label">Imported</span>
        </div>
        <div className={`bi-result-stat ${hasErrors ? "bi-result-stat--error" : "bi-result-stat--zero"}`}>
          <span className="bi-stat-num">{result.error_count}</span>
          <span className="bi-stat-label">Failed</span>
        </div>
      </div>

      {hasErrors && (
        <div className="bi-error-report">
          <h3 className="bi-error-report-title">Error Report</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {result.errors.map((e, i) => (
                  <tr key={i}>
                    <td><code>Row {e.row}</code></td>
                    <td className="bi-error-reason">{e.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="bi-error-hint">
            Fix these rows in your spreadsheet and re-import them separately.
          </p>
        </div>
      )}

      <button className="btn btn-secondary" onClick={onReset} type="button">
        Import Another File
      </button>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function BulkImport({ onComplete }) {
  const [file,        setFile]        = useState(null);
  const [preview,     setPreview]     = useState(null);
  const [dragging,    setDragging]    = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [result,      setResult]      = useState(null);
  const [fileError,   setFileError]   = useState(null);

  const handleFile = useCallback((f) => {
    if (!f) return;
    if (!f.name.endsWith(".csv")) {
      setFileError("Only .csv files are accepted.");
      return;
    }
    setFileError(null);
    setFile(f);

    const reader = new FileReader();
    reader.onload = e => {
      const text = e.target.result;
      setPreview(parseCSVPreview(text));
    };
    reader.readAsText(f);
  }, []);

  const onDragOver  = useCallback(e => { e.preventDefault(); setDragging(true); }, []);
  const onDragLeave = useCallback(() => setDragging(false), []);
  const onDrop      = useCallback(e => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }, [handleFile]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);

    try {
      const { data } = await api.post("/api/students/bulk-import/", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
      if (onComplete) onComplete(data);
    } catch (err) {
      setFileError(
        err.response?.data?.error ||
        "Upload failed. Please check the file and try again."
      );
    } finally {
      setUploading(false);
    }
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setFileError(null);
  }

  // ── Missing required columns warning ──────────────────────────────────
  const missingCols = preview
    ? REQUIRED_COLS.filter(c => !preview.headers.includes(c))
    : [];

  return (
    <div className="bi-root">
      <div className="bi-header">
        <div>
          <h2 className="bi-title">Bulk Student Import</h2>
          <p className="bi-sub">
            Upload a CSV to enrol multiple students at once.
            Required columns: {REQUIRED_COLS.join(", ")}.
          </p>
        </div>
        <TemplateDownload />
      </div>

      {result ? (
        <ResultPanel result={result} onReset={reset} />
      ) : (
        <>
          {!file ? (
            <DropZone
              onFile={handleFile}
              dragging={dragging}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
            />
          ) : (
            <div className="bi-file-info">
              <span className="bi-file-icon">📄</span>
              <div>
                <div className="bi-file-name">{file.name}</div>
                <div className="bi-file-meta">
                  {(file.size / 1024).toFixed(1)} KB
                  {preview && ` · ${preview.totalRows} rows`}
                </div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={reset} type="button">
                Remove ✕
              </button>
            </div>
          )}

          {fileError && (
            <div className="bi-file-error" role="alert">⚠ {fileError}</div>
          )}

          {missingCols.length > 0 && (
            <div className="bi-col-warning" role="alert">
              <strong>Missing required columns:</strong>{" "}
              {missingCols.join(", ")}
            </div>
          )}

          {preview && (
            <PreviewTable
              headers={preview.headers}
              rows={preview.rows}
              totalRows={preview.totalRows}
            />
          )}

          {file && (
            <div className="bi-upload-actions">
              <button
                className="btn btn-ghost"
                onClick={reset}
                type="button"
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleUpload}
                disabled={uploading || missingCols.length > 0}
                type="button"
              >
                {uploading && <span className="bi-btn-spinner" />}
                {uploading
                  ? "Importing…"
                  : `Import ${preview?.totalRows || ""} Students`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}