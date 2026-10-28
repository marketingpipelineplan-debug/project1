import { spawn } from 'node:child_process';
const python = process.platform === 'win32' ? 'python' : 'python3';
const publicService = spawn(python, ['server/trend_service.py'], { stdio: 'inherit' });
const backend = spawn(python, ['server/app.py'], { stdio: 'inherit', env: {...process.env, GOODFORM_TREND_SERVICE_URL: process.env.GOODFORM_TREND_SERVICE_URL || 'http://127.0.0.1:4320'} });
const vite = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1'], { stdio: 'inherit' });
let stopping = false;
function stop(code = 0) { if (stopping) return; stopping = true; backend.kill(); vite.kill(); publicService.kill(); process.exitCode = code; }
for (const child of [backend, vite, publicService]) { child.on('error', e => { console.error(e.message); stop(1); }); child.on('exit', code => { if (!stopping) stop(code || 0); }); }
process.on('SIGINT', () => stop()); process.on('SIGTERM', () => stop());
