import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createServer } from 'node:net';
import { createServer as createViteServer } from 'vite';
import path from 'node:path';

const root = process.cwd();
const require = createRequire(import.meta.url);
const configFile = path.join(
  root, 'tests/visible-msr/vite.test.config.mjs'
);
const chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

async function choosePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = address.port;
      server.close(error => error ? reject(error) : resolve(port));
    });
  });
}

async function main() {
  if (!existsSync(chrome)) {
    throw new Error('SAFETY STOP: Approved Chrome unavailable.');
  }

  const port = await choosePort();

  const vite = await createViteServer({
    configFile,
    server: {
      host: '127.0.0.1',
      port,
      strictPort: true,
      proxy: {},
    },
  });

  try {
    await vite.listen();

    const address = vite.httpServer?.address();

    if (
      !address ||
      typeof address === 'string' ||
      address.address !== '127.0.0.1' ||
      address.port !== port ||
      Object.keys(vite.config.server.proxy || {}).length !== 0
    ) {
      throw new Error(
        'SAFETY STOP: Isolated Vite server configuration mismatch.'
      );
    }

    const packagePath = require.resolve(
      '@playwright/test/package.json'
    );

    const packageInfo = JSON.parse(
      readFileSync(packagePath, 'utf8')
    );

    const executableName = packageInfo.bin?.playwright;

    if (
      typeof executableName !== 'string' ||
      !executableName ||
      path.isAbsolute(executableName)
    ) {
      throw new Error('SAFETY STOP: Invalid Playwright executable.');
    }

    const executable = path.resolve(
      path.dirname(packagePath),
      executableName
    );

    if (
      !existsSync(executable) ||
      path.relative(path.dirname(packagePath), executable)
        .startsWith('..')
    ) {
      throw new Error('SAFETY STOP: Playwright executable missing.');
    }

    const baseURL = `http://127.0.0.1:${port}`;

    console.log('ISOLATED TEST SERVER:', baseURL);
    console.log('BACKEND PROXY: DISABLED');
    console.log('APPLICATION NAVIGATION TESTS: STARTING');

    const child = spawn(process.execPath, [
      executable,
      'test',
      'tests/visible-msr/navigation.spec.mjs',
      '--reporter=line',
      '--workers=1',
    ], {
      cwd: root,
      env: {
        ...process.env,
        VERIDIAN_TEST_BASE_URL: baseURL,
        VERIDIAN_TEST_CHROME: chrome,
      },
      stdio: 'inherit',
      shell: false,
    });

    const exitCode = await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', code => resolve(code ?? 1));
    });

    console.log('Playwright exit code:', exitCode);

    if (exitCode !== 0) {
      throw new Error(
        'APPLICATION NAVIGATION REGRESSION FAILED. ' +
        'Inspect the failing scenarios before changing source.'
      );
    }

    console.log('APPLICATION NAVIGATION REGRESSION: PASSED');
  } finally {
    await vite.close();
    console.log('ISOLATED TEST SERVER: STOPPED');
  }
}

await main();