import React, {useEffect, useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import api from '../../services/api';
import './MigrationCentre.css';

const labels = {
  classes: 'Classes and arms', subjects: 'Subjects', students: 'Students',
  staff: 'Teachers', parents: 'Parents and guardians',
  parent_links: 'Parent-child links', assignments: 'Teacher assignments',
  opening_balances: 'Verified opening balances', timetable: 'Timetable entries',
  fee_schedules: 'Fee schedules', standard_topics: 'Academic-standard topics',
  historical_sessions: 'Historical sessions',
  historical_terms: 'Historical terms',
  historical_enrollments: 'Historical student placements',
  historical_results: 'Historical results',
  historical_attendance: 'Historical attendance',
};
const csvCell = value => {
  const raw = String(value ?? '');
  const safe = /^[\s]*[=+@-]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replace(/"/g, '""')}"`;
};

export default function MigrationCentre() {
  const [searchParams] = useSearchParams();
  const requestedDomain = searchParams.get('type') || 'classes';
  const [domains, setDomains] = useState([]);
  const [domain, setDomain] = useState(requestedDomain);
  const [file, setFile] = useState(null);
  const [parsed, setParsed] = useState(null);
  const [mapping, setMapping] = useState({});
  const [report, setReport] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [jobs, setJobs] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [profileName, setProfileName] = useState('');
  const [sourceSystem, setSourceSystem] = useState('');
  const selected = domains.find(item => item.key === domain);

  async function loadCommandCentre() {
    const [jobResult, profileResult, conflictResult] = await Promise.allSettled([
      api.get('/api/migration/jobs/'),
      api.get('/api/migration/mappings/'),
      api.get('/api/migration/conflicts/?status=open'),
    ]);
    if (jobResult.status === 'fulfilled') setJobs(Array.isArray(jobResult.value.data) ? jobResult.value.data : []);
    if (profileResult.status === 'fulfilled') setProfiles(Array.isArray(profileResult.value.data) ? profileResult.value.data : []);
    if (conflictResult.status === 'fulfilled') setConflicts(Array.isArray(conflictResult.value.data) ? conflictResult.value.data : []);
  }

  useEffect(() => {
    api.get('/api/migration/').then(({data}) => {
      setDomains(data.domains);
      if (!data.domains.some(item => item.key === requestedDomain)) setDomain('classes');
    }).catch(() => setError('Could not load migration types. Retry this page.'));
    api.get('/api/school/setup/').then(({data}) => setReadiness(data)).catch(() => {});
    loadCommandCentre();
  }, [requestedDomain]);

  function reset(nextDomain = domain) {
    setDomain(nextDomain); setFile(null); setParsed(null); setMapping({}); setReport(null); setError('');
    setProfileName(''); setSourceSystem('');
  }

  function applyProfile(profileId) {
    const profile = profiles.find(item => String(item.id) === String(profileId));
    if (!profile) return;
    setMapping(profile.mappings || {});
    setProfileName(profile.name || '');
    setSourceSystem(profile.source_system || '');
    setReport(null);
  }

  async function saveMappingProfile() {
    if (!profileName.trim()) {
      setError('Enter a mapping profile name before saving.');
      return;
    }
    setBusy(true); setError('');
    try {
      await api.post('/api/migration/mappings/', {
        domain, name: profileName.trim(), source_system: sourceSystem.trim(), mappings: mapping,
      });
      await loadCommandCentre();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not save this mapping profile.');
    } finally {
      setBusy(false);
    }
  }

  async function resolveConflict(id, action) {
    setBusy(true); setError('');
    try {
      await api.patch('/api/migration/conflicts/', {id, action, resolution: {reviewed_in: 'migration_centre'}});
      await loadCommandCentre();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not update this migration conflict.');
    } finally {
      setBusy(false);
    }
  }

  async function chooseFile(nextFile) {
    setFile(null); setParsed(null); setReport(null); setError('');
    if (!nextFile) return;
    const lower = nextFile.name.toLowerCase();
    if (!(lower.endsWith('.csv') || lower.endsWith('.xlsx')) || nextFile.size > 2 * 1024 * 1024) {
      setError('Choose a CSV or Excel .xlsx file of at most 2 MB.'); return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append('file', nextFile);
      const {data} = await api.post(`/api/migration/${domain}/inspect/`, form);
      setParsed({
        headers: data.headers || [],
        rows: data.rows || [],
        rowNumbers: data.row_numbers || [],
        totalRows: data.total_rows || 0,
        format: data.format,
        jobId: data.job_id,
        fingerprint: data.file_fingerprint,
      });
      setMapping(data.suggested_mapping || {});
      setFile(nextFile);
    } catch (err) {
      setError(err.response?.data?.error || 'Could not read the spreadsheet.');
    } finally {
      setBusy(false);
    }
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
        await loadCommandCentre();
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
      parsed.headers.map(header => csvCell(parsed.rows[parsed.rowNumbers.indexOf(item.row)]?.[header])).join(','))];
    const url = URL.createObjectURL(new Blob([lines.join('\r\n')], {type: 'text/csv'}));
    const anchor = document.createElement('a'); anchor.href = url;
    anchor.download = `paideia_${domain}_rejected.csv`; anchor.click(); URL.revokeObjectURL(url);
  }

  return <main className="migration-centre">
    <header><p>GET YOUR SCHOOL READY</p><h1>Migration command centre</h1>
      <p>Move current operations and verified historical evidence into Paideia without overwriting conflicts or fabricating school records.</p></header>
    {readiness && <section aria-label="School readiness"><h2>School readiness</h2>
      <p>{readiness.steps.filter(step => step.complete).length} of {readiness.steps.length} setup checks complete.</p>
      <ul>{readiness.steps.filter(step => !step.complete).map(step => <li key={step.key}>{step.label} needs attention</li>)}</ul>
      {!!readiness.missing_assignments && <p>{readiness.missing_assignments} class and subject combinations need a teacher.</p>}
    </section>}
    <section><h2>1. Choose data type</h2><p>Start with foundation and people, then historical sessions, terms and placements before importing historical results or attendance. Import verified opening balances only after student identities are settled.</p>
      <label>Data type <select value={domain} onChange={event => reset(event.target.value)}>
        {domains.map(item => <option key={item.key} value={item.key}>{labels[item.key]}</option>)}</select></label>
      <button type="button" onClick={template} disabled={!selected || busy}>Download CSV template</button>
      {selected && <p>Required: {selected.required.join(', ')}. Reference students with their source student_ref; no Paideia database IDs or passwords.</p>}
      {domain === 'opening_balances' && <p>One verified balance per student. Direction is debt or credit. Amount is nonnegative; zero is allowed when verified. Effective date and source reference preserve provenance. Historical payments stay as existing receipts.</p>}
      {domain === 'timetable' && <p>Uses the current term. Period may be the exact period name or its order number. Teachers must already be assigned to the class and subject.</p>}
      {domain === 'fee_schedules' && <p>Uses the current term. Fee categories and class levels must already exist. Existing schedules with different amounts are rejected for manual review.</p>}
      {domain === 'standard_topics' && <p>Imports into an existing draft academic standard. Objectives are separated with semicolons; approved standards are never edited by import.</p>}
      {domain === 'historical_sessions' && <p>Historical sessions are created non-current. They can never silently replace the school's active session.</p>}
      {domain === 'historical_terms' && <p>Historical terms must fit inside an existing imported session and are created non-current.</p>}
      {domain === 'historical_enrollments' && <p>Historical placement writes SessionEnrollment evidence. Past placements never rewrite current_class.</p>}
      {domain === 'historical_results' && <p>Historical results require matching historical placement and the actual stored assessment components. Conflicts go to human review.</p>}
      {domain === 'historical_attendance' && <p>Import dated attendance evidence only. Paideia does not manufacture daily attendance from aggregate percentages.</p>}
    </section>
    <section><h2>2. Upload and map columns</h2>
      <label>Spreadsheet file <input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={busy} onChange={event => chooseFile(event.target.files[0])}/></label>
      <p>Upload CSV or Excel (.xlsx), up to 2 MB and 2,000 data rows. Excel imports use the first worksheet.</p>
      {parsed && <><p>{parsed.totalRows} rows found. Review each suggested mapping.</p>
        <div className="migration-mapping">{parsed.headers.map(header => <label key={header}>{header}
          <select value={mapping[header] || ''} onChange={event => changeMapping(header, event.target.value)}>
            <option value="">Ignore this column</option>
            {selected?.columns.map(field => <option key={field} value={field}>{field}{selected.required.includes(field) ? ' (required)' : ''}</option>)}
          </select></label>)}</div>
        <p>Unmapped columns are ignored. System fields such as IDs, roles and passwords are rejected by the server.</p>
        <div className="migration-profile-tools">
          <label>Saved mapping
            <select defaultValue="" onChange={event => applyProfile(event.target.value)}>
              <option value="">Choose a saved mapping</option>
              {profiles.filter(item => item.domain === domain).map(item =>
                <option key={item.id} value={item.id}>{item.name}{item.source_system ? ` — ${item.source_system}` : ''}</option>)}
            </select>
          </label>
          <label>Profile name<input value={profileName} onChange={event => setProfileName(event.target.value)} placeholder="e.g. Legacy SIS student export" /></label>
          <label>Source system<input value={sourceSystem} onChange={event => setSourceSystem(event.target.value)} placeholder="Optional" /></label>
          <button type="button" disabled={busy || !profileName.trim()} onClick={saveMappingProfile}>Save mapping profile</button>
        </div>
      </>}
    </section>
    {file && <section><h2>3. Validate and confirm</h2>
      <button disabled={busy} onClick={() => send('validate')}>{busy ? 'Working…' : 'Validate file'}</button>
      {report?.mode === 'validate' && <button disabled={busy || !report.counts.CREATE} onClick={() => send('import')}>Confirm import</button>}
      {report && <div role="status"><h3>{report.mode === 'validate' ? 'Validation' : 'Import'} result</h3>
        <p>Total {report.total_rows}; create {report.counts.CREATE}; reuse {report.counts.REUSE}; review {report.counts.REVIEW || 0}; reject {report.counts.REJECT}.</p>
        {report.job_id && <p>Migration job #{report.job_id} · fingerprint <code>{String(report.file_fingerprint || '').slice(0, 12)}</code></p>}
        {report.warnings.map(warning => <p key={warning}>Warning: {warning}</p>)}
        {!!report.counts.REVIEW && <><h4>Needs human review</h4><ul>{report.rows.filter(row => row.action === 'REVIEW').map(row =>
          <li key={`review-${row.row}`}>Row {row.row} — {row.field}: {row.reason}</li>)}</ul>
          <p>Conflicting historical evidence is held in the reconciliation queue and is never overwritten automatically.</p></>}
        {!!report.counts.REJECT && <><ul>{report.rows.filter(row => row.action === 'REJECT').map(row =>
          <li key={row.row}>Row {row.row} — {row.field}: {row.reason}</li>)}</ul>
          <button onClick={downloadRejected}>Download rejected rows</button>
          <p>Correct these rows in your source file, then validate and import the corrected rows again.</p></>}
        {report.mode === 'import' && <p>Import complete. Existing matching records were reused and were not overwritten.</p>}
      </div>}
    </section>}
    <section aria-label="Migration history"><h2>4. Migration history</h2>
      {jobs.length === 0 ? <p>No migration jobs recorded yet.</p> :
        <div className="migration-job-list">{jobs.slice(0, 20).map(job => <article key={job.id}>
          <div><strong>#{job.id} {labels[job.domain] || job.domain}</strong><span className={`migration-status status-${job.status}`}>{job.status.replaceAll('_', ' ')}</span></div>
          <p>{job.original_filename} · {job.total_rows} rows</p>
          <small>{job.create_count} created · {job.reuse_count} reused · {job.review_count} review · {job.reject_count} rejected</small>
        </article>)}</div>}
    </section>
    <section aria-label="Reconciliation queue"><h2>5. Reconciliation queue</h2>
      {conflicts.length === 0 ? <p>No open migration conflicts.</p> :
        <div className="migration-conflicts">{conflicts.map(conflict => <article key={conflict.id}>
          <strong>Row {conflict.row_number} · {conflict.conflict_type.replaceAll('_', ' ')}</strong>
          <p>{conflict.source_identity || 'Source record needs review'}</p>
          {conflict.candidate_matches?.length > 0 && <pre>{JSON.stringify(conflict.candidate_matches, null, 2)}</pre>}
          <button disabled={busy} onClick={() => resolveConflict(conflict.id, 'resolved')}>Mark resolved</button>
          <button disabled={busy} onClick={() => resolveConflict(conflict.id, 'ignored')}>Ignore conflict</button>
        </article>)}</div>}
    </section>
    {error && <p role="alert">{error}</p>}
    <p>Opening balances require human verification before import. Historical payments are never converted into Paideia payment orders, Paystack settlements or new receipts.</p>
  </main>;
}
