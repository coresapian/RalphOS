#!/usr/bin/env node
import { spawn, execSync } from 'child_process';
import { existsSync, mkdirSync, cpSync } from 'fs';
import { tmpdir, homedir, platform } from 'os';
import { join } from 'path';

const useProfile = process.argv.includes('--profile');

function getChromePath() {
  const paths = {
    darwin: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    win32: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    linux: '/usr/bin/google-chrome'
  };
  return paths[platform()] || paths.linux;
}

function getDefaultProfilePath() {
  const paths = {
    darwin: join(homedir(), 'Library/Application Support/Google/Chrome'),
    win32: join(homedir(), 'AppData/Local/Google/Chrome/User Data'),
    linux: join(homedir(), '.config/google-chrome')
  };
  return paths[platform()] || paths.linux;
}

async function isAlreadyRunning() {
  try {
    const res = await fetch('http://localhost:9222/json/version');
    return res.ok;
  } catch {
    return false;
  }
}

async function main() {
  if (await isAlreadyRunning()) {
    console.log('✓ Chrome already running on :9222');
    process.exit(0);
  }

  const chromePath = getChromePath();
  if (!existsSync(chromePath)) {
    console.error('✗ Chrome not found at:', chromePath);
    process.exit(1);
  }

  const userDataDir = join(tmpdir(), `chrome-debug-${Date.now()}`);
  mkdirSync(userDataDir, { recursive: true });

  if (useProfile) {
    const defaultProfile = getDefaultProfilePath();
    if (existsSync(defaultProfile)) {
      console.log('Copying profile data (this may take a moment)...');
      try {
        cpSync(join(defaultProfile, 'Default'), join(userDataDir, 'Default'), { recursive: true });
        cpSync(join(defaultProfile, 'Local State'), join(userDataDir, 'Local State'));
      } catch (e) {
        console.log('Note: Some profile files could not be copied, continuing with partial profile');
      }
    }
  }

  const args = [
    '--remote-debugging-port=9222',
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check'
  ];

  const chrome = spawn(chromePath, args, {
    detached: true,
    stdio: 'ignore'
  });
  chrome.unref();

  // Wait for Chrome to start
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 500));
    if (await isAlreadyRunning()) {
      console.log(`✓ Chrome started on :9222${useProfile ? ' with your profile' : ''}`);
      process.exit(0);
    }
  }

  console.error('✗ Chrome failed to start within timeout');
  process.exit(1);
}

main();
