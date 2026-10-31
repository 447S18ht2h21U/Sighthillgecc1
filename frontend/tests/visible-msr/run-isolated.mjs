import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createServer } from 'node:net';
import { chromium } from '@playwright/test';
import { createServer as createViteServer } from 'vite';
import path from 'node:path';

const root = process.cwd();
const require = createRequire(import.meta.url);

const configFile = path.join(
  root, 'tests/visible-msr/vite.test.config.mjs'
);

const chromeExecutable =
  'C:/Program Files/Google/Chrome/Application/chrome.exe';

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
  if (!existsSync(chromeExecutable)) {
    throw new Error('SAFETY STOP: Approved Chrome unavailable.');
  }

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
        'SAFETY STOP: Isolated server or backend proxy mismatch.'
      );
    }

    const baseURL = `http://127.0.0.1:${port}`;

    console.log('ISOLATED TEST SERVER:', baseURL);
    console.log('LISTENING ADDRESS: VERIFIED');
    console.log('BACKEND PROXY: DISABLED');

    browser = await chromium.launch({
      headless: true,
      executablePath: chromeExecutable,
    });

    const page = await browser.newPage();

    try {
      await page.goto(
        `${baseURL}/tests/visible-msr/index.html`
      );

      await page.getByRole('region', {
        name: 'Visible Master Sales Records',
      }).waitFor();

      const initialRequests = await page.evaluate(
        () => window.veridianMSRTest.pending()
      );

      if (
        initialRequests.length !== 1 ||
        initialRequests[0].path !== 'visible-msrs/?page=1' ||
        initialRequests[0].method !== 'GET'
      ) {
        throw new Error(
          'SAFETY STOP: Synthetic API harness contract mismatch.'
        );
      }

      console.log('REACT HARNESS: VERIFIED');
      console.log('SYNTHETIC API: GET ONLY');
    } finally {
      await page.close();
    }

    await browser.close();
    browser = undefined;

    const packageFile = require.resolve(
      '@playwright/test/package.json'
    );

    const packageInfo = JSON.parse(
      readFileSync(packageFile, 'utf8')
    );

    const executableName = packageInfo.bin?.playwright;

    if (
      typeof executableName !== 'string' ||
      !executableName ||
      path.isAbsolute(executableName)
    ) {
      throw new Error(
        'SAFETY STOP: Invalid Playwright executable declaration.'
      );
    }

    const executable = path.resolve(
      path.dirname(packageFile),
      executableName
    );

    const relativeExecutable = path.relative(
      path.dirname(packageFile),
      executable
    );

    if (
      relativeExecutable.startsWith('..') ||
      path.isAbsolute(relativeExecutable) ||
      !existsSync(executable)
    ) {
      throw new Error(
        'SAFETY STOP: Playwright executable unavailable.'
      );
    }

    console.log('PLAYWRIGHT EXECUTABLE: VERIFIED');
    console.log('EXECUTING EIGHT SYNTHETIC BROWSER SCENARIOS');

    const child = spawn(process.execPath, [
      executable,
      'test',
      'tests/visible-msr/visible-msr.spec.mjs',
      '--reporter=line',
      '--workers=1',
    ], {
      cwd: root,
      env: {
        ...process.env,
        VERIDIAN_TEST_BASE_URL: baseURL,
        VERIDIAN_TEST_CHROME: chromeExecutable,
      },
      stdio: 'inherit',
      shell: false,
    });

    const exitCode = await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', code => resolve(code ?? 1));
    });

    if (exitCode !== 0) {
      throw new Error(
        'SAFETY STOP: Browser regression failed with exit code ' +
        exitCode
      );
    }

    console.log('VISIBLE MSR BROWSER REGRESSION: PASSED');
  } finally {
    await browser?.close();
    await server.close();
    console.log('ISOLATED TEST SERVER: STOPPED');
  }
}

await run();