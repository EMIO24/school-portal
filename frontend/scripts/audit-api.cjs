// Read-only Django path/method contract check. No backend server or database needed.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const root = path.resolve(__dirname, '../..');
function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', cwd: root, ...options });
  if (result.error || result.status !== 0) {
    console.error(result.error || result.stderr || result.stdout);
    process.exit(result.status || 1);
  }
  return result.stdout;
}
const candidates = run(process.execPath, [path.join(__dirname, 'list-api-routes.cjs')]);
const output = run(process.env.PYTHON || 'python', [path.join(__dirname, 'check-api-routes.py')], { input: candidates });
const rows = JSON.parse(output);
fs.writeFileSync(path.join(root, 'frontend/api-route-results.json'), JSON.stringify(rows, null, 2));
const failures = rows.filter(row => !row.resolves || !row.method_allowed);
for (const row of failures) console.error(`${row.file}:${row.line} ${row.method} ${row.path}`);
console.log(`${rows.length} request variants checked; ${failures.length} path/method failures.`);
process.exitCode = failures.length ? 1 : 0;
