import { downloadReport } from '../../services/pdf';
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
  "first_name","last_name",
  "gender","dob","class_level",
  "guardian_name","guardian_phone",
];

const OPTIONAL_COLS = [
  "email",
  "state_of_origin","religion",
  "guardian_email","guardian_relationship",
];

// ── CSV parser (client-side preview only) ─────────────────────────────────

export function parseCSVPreview(text, maxRows = 5) {
  const records = [];
  let record = [], value = '', quoted = false;
  const input = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];
    if (char === '"') {
      if (quoted && input[i + 1] === '"') { value += '"'; i += 1; }
      else quoted = !quoted;
    } else if (!quoted && (char === ',' || char === '\n' || char === '\r')) {
      record.push(value.trim()); value = '';
      if (char !== ',') {
        if (record.some(cell => cell !== '')) records.push(record);
        record = [];
        if (char === '\r' && input[i + 1] === '\n') i += 1;
      }
    } else value += char;
  }
  if (quoted) throw new Error('A quoted CSV field is not closed.');
  record.push(value.trim());
  if (record.some(cell => cell !== '')) records.push(record);
  const [headers = [], ...data] = records;
  if (headers.some(h => !h) || new Set(headers).size !== headers.length) {
    throw new Error('CSV column names must be non-empty and unique.');
  }
  if (data.some(row => row.length !== headers.length)) {
    throw new Error('Every CSV row must have the same number of columns as the header.');
  }
  return {
    headers,
    rows: data.slice(0, maxRows).map(row => Object.fromEntries(headers.map((h, i) => [h, row[i]]))),
    totalRows: data.length,
  };
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

function TemplateDownload({ columns, exampleRow, templateName }) {
  function download() {
    const headers = columns.join(",");
    const example = exampleRow;
    downloadReport('Import file guide', [
      'Create a CSV file with the following header and sample row.',
      'Header:', headers, '', 'Sample row:', example,
      '', 'Replace the sample values with your records and save as a .csv file to upload.',
    ], templateName.replace(/\.csv$/i, '.pdf'));

  }

  return (
    <button className="btn btn-ghost btn-sm bi-template-btn" onClick={download} type="button">
      ↓ Download PDF Guide
    </button>
  );
}

function PreviewTable({ headers, rows, totalRows, requiredCols }) {
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
                <th key={h} className={requiredCols.includes(h) ? "bi-col-required" : ""}>
                  {h}
                  {requiredCols.includes(h) && <span className="bi-req-dot" title="Required" />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {headers.map(h => (
                  <td key={h} className={!row[h] && requiredCols.includes(h) ? "bi-cell-missing" : ""}>
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

export default function BulkImport({
  onComplete,
  endpoint = '/api/students/bulk-import/',
  requiredCols = REQUIRED_COLS,
  templateCols = [...REQUIRED_COLS, ...OPTIONAL_COLS],
  exampleRow = 'Amaka,Okonkwo,female,2008-05-14,JSS1,Mrs Okonkwo,08012345678,,Lagos,Christianity,parent@example.com,mother',
  title = 'Bulk Student Import',
  entityLabel = 'Students',
  templateName = 'student_import_template.csv',
}) {
  const [file,        setFile]        = useState(null);
  const [preview,     setPreview]     = useState(null);
  const [dragging,    setDragging]    = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [result,      setResult]      = useState(null);
  const [fileError,   setFileError]   = useState(null);

  const readVersion = useRef(0);

  const handleFile = useCallback((f) => {
    if (!f) return;
    const version = ++readVersion.current;
    setFile(null);
    setPreview(null);
    if (!f.name.toLowerCase().endsWith(".csv")) {
      setFileError("Only .csv files are accepted.");
      return;
    }
    setFileError(null);
    setFile(f);

    const reader = new FileReader();
    reader.onload = e => {
      if (version !== readVersion.current) return;
      try { setPreview(parseCSVPreview(e.target.result)); }
      catch (error) { setFileError(error.message); }
    };
    reader.onerror = () => {
      if (version === readVersion.current) setFileError('Could not read this file. Please select it again.');
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
    if (!file || !preview?.totalRows || uploading) return;
    setUploading(true);
    setFileError(null);
    const fd = new FormData();
    fd.append("file", file);

    try {
      const { data } = await api.post(endpoint, fd, {
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
    readVersion.current += 1;
    setFile(null);
    setPreview(null);
    setResult(null);
    setFileError(null);
  }

  // ── Missing required columns warning ──────────────────────────────────
  const missingCols = preview
    ? requiredCols.filter(c => !preview.headers.includes(c))
    : [];

  return (
    <div className="bi-root">
      <div className="bi-header">
        <div>
          <h2 className="bi-title">{title}</h2>
          <p className="bi-sub">
            Upload multiple records from a CSV file.
            Required columns: {requiredCols.join(", ")}.
          </p>
        </div>
        <TemplateDownload columns={templateCols} exampleRow={exampleRow} templateName={templateName} />
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
              requiredCols={requiredCols}
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
                disabled={uploading || !preview?.totalRows || missingCols.length > 0}
                type="button"
              >
                {uploading && <span className="bi-btn-spinner" />}
                {uploading
                  ? "Importing…"
                  : `Import ${preview?.totalRows || ""} ${entityLabel}`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
