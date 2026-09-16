// Dedicated browser-test frontend; does not modify the user's .env files.
const { spawn } = require('child_process');
const path = require('path');
const child = spawn(process.execPath, [require.resolve('react-scripts/scripts/start')], {
  cwd: path.resolve(__dirname, '..'), stdio: 'inherit',
  env: { ...process.env, HOST: '127.0.0.1', PORT: '3001', BROWSER: 'none',
    REACT_APP_API_URL: 'http://127.0.0.1:8001', REACT_APP_SCHOOL_SLUG: process.env.INTEGRATION_SCHOOL || 'qa-school',
    REACT_APP_CLOUDINARY_CLOUD_NAME: '', REACT_APP_CLOUDINARY_UPLOAD_PRESET: '',
  },
});
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
