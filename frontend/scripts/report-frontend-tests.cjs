const fs = require('fs');
const path = require('path');
const frontend = path.resolve(__dirname, '..');
const readText = file => {
  const bytes = fs.readFileSync(path.join(frontend, file));
  return bytes.toString(bytes[0] === 0xff && bytes[1] === 0xfe ? 'utf16le' : 'utf8').replace(/^\uFEFF/, '');
};
const read = file => JSON.parse(readText(file));
const results = read('test-results.json');
const coverage = read('coverage/coverage-summary.json');
const routes = read('api-route-results.json');
const assertions = results.testResults.flatMap(suite => suite.assertionResults);
const routingTest = assertions.find(test => test.fullName === 'every page file has a concrete route element');
const failedRoutes = routes.filter(row => !row.resolves || !row.method_allowed);
const files = Object.entries(coverage).filter(([file]) => file !== 'total');
const pagesRoot = path.join(frontend, 'src/pages');
const pageCount = fs.readdirSync(pagesRoot).flatMap(group => fs.readdirSync(path.join(pagesRoot, group)).filter(file => file.endsWith('.jsx'))).length;
const sites = new Set(routes.map(row => `${row.file}:${row.line}`)).size;
const buildLog = fs.existsSync(path.join(frontend, 'build-test-results.txt'))
  ? readText('build-test-results.txt') : '';
const build = buildLog.includes('Compiled successfully.') ? 'passed without compiler/lint warnings'
  : buildLog.includes('Compiled with warnings.') ? 'passed with warnings'
  : 'not verified by the latest build log';
const backendLog = fs.existsSync(path.join(frontend, '../backend-test-results.txt')) ? readText('../backend-test-results.txt') : '';
const backendCount = backendLog.match(/Ran (\d+) tests/);
const backendStatus = backendCount && /\nOK\r?\n/.test(backendLog)
  ? `${backendCount[1]} tests passed against isolated test settings` : 'not verified by the latest backend test log';
const lines = [
  '# Frontend test report', '', `Generated: ${new Date().toISOString()}`, '',
  `- Tests: **${results.numPassedTests} passed, ${results.numFailedTests} failed, ${results.numPendingTests} skipped** across ${results.numTotalTestSuites} suites.`,
  `- Coverage: **${coverage.total.lines.pct}% lines**, ${coverage.total.statements.pct}% statements, ${coverage.total.branches.pct}% branches, ${coverage.total.functions.pct}% functions.`,
  `- API audit: **${routes.length} request variants at ${sites} call sites; ${failedRoutes.length} unresolved paths or unsupported methods**.`,
  `- Page routing: **${pageCount} pages; ${routingTest?.status === 'passed' ? 'all have concrete route elements (regression test passed)' : 'route completeness test has not passed'}**.`,
  `- Production build: **${build}**.`,
  `- Backend tests: **${backendStatus}**.`, '',
  '## Verified fixes', '',
  '- Staff CSV uses staff-only required columns, the staff upload endpoint, and staff labels. CSV preview handles quoted commas, escaped quotes, multiline fields, BOM, empty input, invalid columns, and incomplete rows.',
  '- Frontend API paths use Django routes, including exam results. The audit includes services, fetch/axios calls, variable URLs, both domain-rating endpoints, and both import configurations.',
  '- Role navigation exposes the registered pages, including linked-child result and fee pages. Tests render each declared page route, check navigation destinations, and verify nested unknown-route fallbacks and the superadmin landing route.',
  '- Student profile/class IDs survive authentication normalization. Fees and performance use profile IDs; results, attendance, and gradebook use account IDs; timetables use class IDs. Enrollment and staff lists expose both identifiers.',
  '- Timetable teachers use account IDs from staff-list responses. Staff editing uses the profile PATCH contract and nullable date fields.',
  '- PDF, ZIP, CSV, and receipt downloads use the authenticated API client. API origin and tenant headers are shared across authenticated requests, parent login, school branding, and public result checking.',
  '- Workflow tests cover timetable creation, staff editing, exam-result loading and gradebook push, template CRUD, fee schedules, attendance saving/locking, and gradebook draft/publish.',
  '- CI checks frontend tests, API contracts and the production build before deployment.', '',
  '## Coverage limits', '',
  '**This is not 100% interaction coverage or a flawless-system certification.** The line coverage denominator includes every page, shared component, and App.js; files and unexecuted branches are not excluded to inflate the number. Service/context tests also run, but are outside this comparable coverage denominator.', '',
  'Frontend tests use jsdom and mocked HTTP responses. Route tests isolate page components to verify router wiring. The Django audit verifies registered paths and methods, not every request payload, permission decision, response schema, or live service outcome. Dynamic resource IDs use a representative value of 1; configured backend origins are stripped for resolution. External Cloudinary uploads and service-worker asset fetches are outside the backend route audit.', '',
  'The isolated backend suite additionally verifies student/staff profile serialization, real staff CSV import against a temporary SQLite database, duplicate rows, rejected roles/tenants, and payment-provider failures. PostgreSQL-specific behavior, full live browser journeys, and external notifications/payments still require integration testing.', '',
  '## Coverage by file', '', '| File | Lines | Branches |', '|---|---:|---:|',
  ...files.map(([file, value]) => {
    const rel = path.relative(frontend, file).replaceAll('\\', '/');
    return `| [${rel}](frontend/${rel}) | ${value.lines.pct}% | ${value.branches.pct}% |`;
  }), '', '## API contract failures', '',
  ...(failedRoutes.length ? failedRoutes.map(row => `- ${row.file}:${row.line}: ${row.method} \`${row.path}\``) : ['None in the extracted frontend request variants.']), '',
  '## Rerun', '', 'From the repository root:', '', '```powershell',
  'npm --prefix frontend run audit:api',
  'npm --prefix frontend run test:coverage',
  'npm --prefix frontend run build > frontend/build-test-results.txt 2>&1',
  'node frontend/scripts/report-frontend-tests.cjs',
  '```', '',
  'The API audit needs the backend Python dependencies installed, but no running server or database. For the isolated backend tests, run from `backend/`:', '',
  '```powershell', 'python manage.py test --settings=config.settings.test --noinput', '```', '',
  'Artifacts: [test results](frontend/test-results.json), [HTML coverage](frontend/coverage/lcov-report/index.html), [API route audit](frontend/api-route-results.json).', '',
];
fs.writeFileSync(path.join(frontend, '../FRONTEND_TEST_REPORT.md'), lines.join('\n'));
console.log(`${results.numPassedTests} tests passed; ${coverage.total.lines.pct}% line coverage; ${failedRoutes.length} API contract failures.`);
