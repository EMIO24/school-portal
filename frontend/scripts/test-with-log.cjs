const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const root = path.resolve(__dirname, '..', '..');
const logDir = path.join(root, 'test-logs');
fs.mkdirSync(logDir, { recursive: true });

const stamp = new Date().toISOString()
  .replace(/[-:]/g, '')
  .replace(/\..+/, '')
  .replace('T', '-');

const logPath = path.join(logDir, `frontend-${stamp}.txt`);
const latestPath = path.join(logDir, 'frontend-latest.txt');
const log = fs.createWriteStream(logPath, { encoding: 'utf8' });

function mirror(chunk, stream) {
  stream.write(chunk);
  log.write(chunk);
}

process.stdout.write(`[test-log] frontend output: ${logPath}\n`);

const reactScripts = require.resolve('react-scripts/bin/react-scripts.js');
const child = spawn(process.execPath, [reactScripts, 'test', ...process.argv.slice(2)], {
  cwd: path.resolve(__dirname, '..'),
  env: { ...process.env, FORCE_COLOR: '0' },
  stdio: ['inherit', 'pipe', 'pipe'],
});

child.stdout.on('data', chunk => mirror(chunk, process.stdout));
child.stderr.on('data', chunk => mirror(chunk, process.stderr));

child.on('error', error => {
  const message = `\n[test-log] failed to start frontend tests: ${error.stack || error.message}\n`;
  mirror(message, process.stderr);
  log.end(() => process.exit(1));
});

child.on('close', code => {
  log.end(() => {
    try {
      fs.copyFileSync(logPath, latestPath);
      process.stdout.write(`[test-log] latest frontend log: ${latestPath}\n`);
    } finally {
      process.exit(code ?? 1);
    }
  });
});
