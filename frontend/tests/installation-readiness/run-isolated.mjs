import { spawn } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createServer } from 'node:net';
import { chromium } from '@playwright/test';
import { createServer as createViteServer } from 'vite';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const root = process.cwd();
const require = createRequire(import.meta.url);
const configFile = path.join(
  root, 'tests/installation-readiness/vite.test.config.mjs'
);

async function choosePort() {
  return await new Promise((resolve, reject) => {
    const probe = createServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address();
      const port = address.port;
      probe.close(error => error ? reject(error) : resolve(port));
    });
  });
}

async function run() {
  const port = await choosePort();
  const server = await createViteServer({
    configFile,
    server: {
      host: '127.0.0.1',
      port,
      strictPort: true,
      proxy: {},
    },
  });

  let browser;
  try {
    await server.listen();

    const address = server.httpServer?.address();
    const proxy = server.config.server.proxy || {};

    if (
      !address ||
      typeof address === 'string' ||
      address.address !== '127.0.0.1' ||
      address.port !== port ||
      Object.keys(proxy).length !== 0
    ) {
      throw new Error(
        'SAFETY STOP: Isolated test server address or proxy mismatch.'
      );
    }

    const baseURL = `http://127.0.0.1:${port}`;
    console.log('ISOLATED TEST SERVER:', baseURL);
    console.log('LISTENING ADDRESS: VERIFIED');
    console.log('BACKEND PROXY: DISABLED');

    const chromeExecutable = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

    if (!existsSync(chromeExecutable)) {
      throw new Error('SAFETY STOP: Installed Chrome unavailable.');
    }

    browser = await chromium.launch({
      headless: true,
      executablePath: chromeExecutable,
    });

    const page = await browser.newPage();
    await page.goto(`${baseURL}/tests/installation-readiness/index.html`);

    if (!await page.getByRole('heading', {
      name: 'Schedule an installation',
    }).isVisible()) {
      throw new Error('Test harness failed to load.');
    }

    await page.close();
    await browser.close();
    browser = undefined;

    const packageFile = require.resolve('@playwright/test/package.json');
    const packageInfo = JSON.parse(readFileSync(packageFile, 'utf8'));
    const executableName = packageInfo.bin?.playwright;

    if (
      typeof executableName !== 'string' ||
      !executableName ||
      path.isAbsolute(executableName)
    ) {
      throw new Error('SAFETY STOP: Invalid Playwright executable declaration.');
    }

    const executable = path.resolve(
      path.dirname(packageFile),
      executableName
    );

    const packageDirectory = path.dirname(packageFile);
    const relativeExecutable = path.relative(packageDirectory, executable);

    if (
      relativeExecutable.startsWith('..') ||
      path.isAbsolute(relativeExecutable) ||
      !existsSync(executable)
    ) {
      throw new Error('SAFETY STOP: Playwright executable unavailable.');
    }

    console.log('PLAYWRIGHT EXECUTABLE: VERIFIED');

    const child = spawn(process.execPath, [
      executable,
      'test',
      'tests/installation-readiness/installation-readiness.spec.mjs',
      '--reporter=line',
      '--workers=1',
    ], {
      cwd: root,
      env: {
        ...process.env,
        VERIDIAN_TEST_BASE_URL: baseURL,
        VERIDIAN_TEST_CHROME: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
      },
      stdio: 'inherit',
      shell: false,
    });

    const exitCode = await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', code => resolve(code ?? 1));
    });

    if (exitCode !== 0) {
      throw new Error('Playwright tests failed with exit code ' + exitCode);
    }

    console.log('ISOLATED PLAYWRIGHT TESTS: PASS');
  } finally {
    await browser?.close();
    await server.close();
    console.log('ISOLATED TEST SERVER: STOPPED');
  }
}

await run();
