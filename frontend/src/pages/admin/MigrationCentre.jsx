import React, {useEffect, useState} from 'react';
import api from '../../services/api';
import {parseCSVPreview} from '../../components/admin/BulkImport';
import './MigrationCentre.css';

const labels = {
  classes: 'Classes and arms', subjects: 'Subjects', students: 'Students',
  staff: 'Teachers', parents: 'Parents and guardians',
  parent_links: 'Parent-child links', assignments: 'Teacher assignments',
  opening_balances: 'Verified opening balances',
};
const aliases = {regno: 'student_ref', studentnumber: 'student_ref'};
const normalized = value => value.toLowerCase().replace(/[^a-z0-9]/g, '');
const csvCell = value => {
  const raw = String(value ?? '');
  const safe = /^[\s]*[=+@-]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replace(/"/g, '""')}"`;
};

export default function MigrationCentre() {
  const [domains, setDomains] = useState([]);
  const [domain, setDomain] = useState('classes');
  const [file, setFile] = useState(null);
  const [parsed, setParsed] = useState(null);
  const [mapping, setMapping] = useState({});
  const [report, setReport] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selected = domains.find(item => item.key === domain);

  useEffect(() => {
    api.get('/api/migration/').then(({data}) => setDomains(data.domains)).catch(() => setError('Could not load migration types. Retry this page.'));
    api.get('/api/school/setup/').then(({data}) => setReadiness(data)).catch(() => {});
  }, []);

  function reset(nextDomain = domain) {
    setDomain(nextDomain); setFile(null); setParsed(null); setMapping({}); setReport(null); setError('');
  }

  async function chooseFile(nextFile) {
    setFile(null); setParsed(null); setReport(null); setError('');
    if (!nextFile) return;
    if (!nextFile.name.toLowerCase().endsWith('.csv') || nextFile.size > 2 * 1024 * 1024) {
      setError('Choose a CSV file of at most 2 MB.'); return;
    }
    try {
      const text = await nextFile.text();
      const preview = parseCSVPreview(text, 2000);
      if (preview.totalRows > 2000) throw new Error('Import at most 2,000 rows per file.');
      const suggested = {};
      for (const header of preview.headers) {
        const match = selected?.columns.find(field => normalized(field) === normalized(header)) || aliases[normalized(header)];
        if (match && selected?.columns.includes(match) && !Object.values(suggested).includes(match)) suggested[header] = match;
      }
      setParsed(preview); setMapping(suggested); setFile(nextFile);
    } catch (err) {setError(err.message || 'Could not read the CSV.');}
  }

  function changeMapping(header, field) {
    const next = {...mapping};
    next[header] = field || null;
    setMapping(next); setReport(null);
  }

  async function template() {
    setError('');
    try {
      const {data} = await api.get(`/api/migration/templates/${domain}/`, {responseType: 'blob'});
      const url = URL.createObjectURL(new Blob([data], {type: 'text/csv'}));
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `paideia_${domain}_template.csv`; anchor.click();
      URL.revokeObjectURL(url);
    } catch {setError('Could not download the template. Try again.');}
  }

  async function send(operation) {
    if (busy || !file) return;
    if (operation === 'import' && !window.confirm(`Import ${report?.counts.CREATE || 0} new ${labels[domain].toLowerCase()} records? Reused records will not be overwritten.`)) return;
    setBusy(true); setError('');
    const form = new FormData(); form.append('file', file); form.append('mapping', JSON.stringify(mapping));
    try {
      const {data} = await api.post(`/api/migration/${domain}/${operation}/`, form);
      setReport(data);
      if (operation === 'import') {
        try {const setup = await api.get('/api/school/setup/'); setReadiness(setup.data);}
        catch {setError('Import completed. School readiness could not refresh; reload this page to check progress.');}
      }
    } catch (err) {
      setReport(null);
      setError(err.response?.data?.error || (operation === 'import'
        ? 'Could not confirm the import. Validate this same file again before retrying; Paideia reuses records already created.'
        : 'Validation could not finish. Check the file and connection, then retry.'));
    } finally {setBusy(false);}
  }

  function downloadRejected() {
    if (!parsed || !report) return;
    const rejected = report.rows.filter(row => row.action === 'REJECT');
    const lines = [parsed.headers.map(csvCell).join(','), ...rejected.map(item =>
      parsed.headers.map(header => csvCell(parsed.rows[item.row - 2]?.[header])).join(','))];
    const url = URL.createObjectURL(new Blob([lines.join('\r\n')], {type: 'text/csv'}));
    const anchor = document.createElement('a'); anchor.href = url;
    anchor.download = `paideia_${domain}_rejected.csv`; anchor.click(); URL.revokeObjectURL(url);
  }

  return <main className="migration-centre">
    <header><p>GET YOUR SCHOOL READY</p><h1>Data migration</h1>
      <p>Import your current school records in order. Validate every file before confirming; only this school's records are used.</p></header>
    {readiness && <section aria-label="School readiness"><h2>School readiness</h2>
      <p>{readiness.steps.filter(step => step.complete).length} of {readiness.steps.length} setup checks complete.</p>
      <ul>{readiness.steps.filter(step => !step.complete).map(step => <li key={step.key}>{step.label} needs attention</li>)}</ul>
      {!!readiness.missing_assignments && <p>{readiness.missing_assignments} class and subject combinations need a teacher.</p>}
    </section>}
    <section><h2>1. Choose data type</h2><p>Foundation: classes, subjects. People: students, teachers, parents. Then link children and assign teachers. Import verified opening balances after student identities are settled.</p>
      <label>Data type <select value={domain} onChange={event => reset(event.target.value)}>
        {domains.map(item => <option key={item.key} value={item.key}>{labels[item.key]}</option>)}</select></label>
      <button type="button" onClick={template} disabled={!selected || busy}>Download CSV template</button>
      {selected && <p>Required: {selected.required.join(', ')}. Reference students with their source student_ref; no Paideia database IDs or passwords.</p>}
      {domain === 'opening_balances' && <p>One verified balance per student. Direction is debt or credit. Amount is nonnegative; zero is allowed when verified. Effective date and source reference preserve provenance. Historical payments stay as existing receipts.</p>}
    </section>
    <section><h2>2. Upload and map columns</h2>
      <label>CSV file <input type="file" accept=".csv,text/csv" onChange={event => chooseFile(event.target.files[0])}/></label>
      {parsed && <><p>{parsed.totalRows} rows found. Review each suggested mapping.</p>
        <div className="migration-mapping">{parsed.headers.map(header => <label key={header}>{header}
          <select value={mapping[header] || ''} onChange={event => changeMapping(header, event.target.value)}>
            <option value="">Ignore this column</option>
            {selected?.columns.map(field => <option key={field} value={field}>{field}{selected.required.includes(field) ? ' (required)' : ''}</option>)}
          </select></label>)}</div>
        <p>Unmapped columns are ignored. System fields such as IDs, roles and passwords are rejected by the server.</p>
      </>}
    </section>
    {file && <section><h2>3. Validate and confirm</h2>
      <button disabled={busy} onClick={() => send('validate')}>{busy ? 'Working…' : 'Validate file'}</button>
      {report?.mode === 'validate' && <button disabled={busy || !report.counts.CREATE} onClick={() => send('import')}>Confirm import</button>}
      {report && <div role="status"><h3>{report.mode === 'validate' ? 'Validation' : 'Import'} result</h3>
        <p>Total {report.total_rows}; create {report.counts.CREATE}; reuse {report.counts.REUSE}; reject {report.counts.REJECT}.</p>
        {report.warnings.map(warning => <p key={warning}>Warning: {warning}</p>)}
        {!!report.counts.REJECT && <><ul>{report.rows.filter(row => row.action === 'REJECT').map(row =>
          <li key={row.row}>Row {row.row} — {row.field}: {row.reason}</li>)}</ul>
          <button onClick={downloadRejected}>Download rejected rows</button>
          <p>Correct these rows in your source file, then validate and import the corrected rows again.</p></>}
        {report.mode === 'import' && <p>Import complete. Existing matching records were reused and were not overwritten.</p>}
      </div>}
    </section>}
    {error && <p role="alert">{error}</p>}
    <p>Opening balances require human verification before import. Do not import old payments as new receipts.</p>
  </main>;
}
