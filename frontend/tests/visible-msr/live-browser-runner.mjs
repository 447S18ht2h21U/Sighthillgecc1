/**
 * VERIDIAN live browser integration runner.
 *
 * Invoked ONLY by Django's isolated live-server test.
 * No API mocking. Vite forwards /api to the supplied temporary server.
 */
import { chromium, expect } from '@playwright/test';
import { createServer as createViteServer } from 'vite';
import { createServer as createTCPServer } from 'node:net';
import { existsSync } from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const djangoURL = process.env.VERIDIAN_ISOLATED_DJANGO_URL || '';
const password = process.env.VERIDIAN_ISOLATED_BROWSER_PASSWORD || '';
const marker = process.env.VERIDIAN_ISOLATED_BROWSER_RUN || '';

if (marker !== 'DJANGO_LIVE_TEST_SQLITE_MEMORY') {
  throw new Error('SAFETY STOP: Django live-test authorization missing.');
}

if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(djangoURL)) {
  throw new Error('SAFETY STOP: Loopback Django test URL required.');
}

const djangoPort = Number(new URL(djangoURL).port);

if (
  !Number.isInteger(djangoPort) ||
  djangoPort < 1024 ||
  djangoPort > 65535 ||
  djangoPort === 8000
) {
  throw new Error('SAFETY STOP: Invalid or reserved Django test port.');
}

if (!password || !existsSync(chrome)) {
  throw new Error('SAFETY STOP: Test credential or Chrome unavailable.');
}

async function choosePort() {
  return new Promise((resolve, reject) => {
    const probe = createTCPServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address();
      probe.close(error => {
        if (error) reject(error);
        else resolve(address.port);
      });
    });
  });
}

async function main() {
  const port = await choosePort();

  const vite = await createViteServer({
    configFile: path.join(
      root, 'tests/visible-msr/vite.test.config.mjs'
    ),
    server: {
      host: '127.0.0.1',
      port,
      strictPort: true,
      proxy: {
        '/api': {
          target: djangoURL,
          changeOrigin: false,
        },
      },
    },
  });

  let browser;

  try {
    await vite.listen();

    const address = vite.httpServer?.address();
    const proxy = vite.config.server.proxy || {};

    if (
      !address ||
      typeof address === 'string' ||
      address.address !== '127.0.0.1' ||
      address.port !== port ||
      Object.keys(proxy).length !== 1 ||
      proxy['/api']?.target !== djangoURL ||
      proxy['/api']?.changeOrigin !== false
    ) {
      throw new Error('SAFETY STOP: Browser proxy configuration mismatch.');
    }

    browser = await chromium.launch({
      headless: true,
      executablePath: chrome,
    });

    const baseURL = `http://127.0.0.1:${port}`;
    console.log('LIVE BROWSER: ISOLATED VITE SERVER VERIFIED');
    console.log('LIVE BROWSER: DJANGO TEST PROXY VERIFIED');
    console.log('LIVE BROWSER: API MOCKS DISABLED');

    async function verifyRole({ username, expectedCount, expectedName, buttonName = "View Master Sales Records", regionName = "Visible Master Sales Records" }) {
      const context = await browser.newContext();
      const page = await context.newPage();
      const observed = [];
      const unexpectedServerErrors = [];

      // Inspect all API responses, including background components.
      // Do not record response bodies, headers, cookies, or credentials.
      page.on('response', response => {
        const endpoint = new URL(response.url()).pathname;
        if (endpoint.startsWith('/api/') && response.status() >= 500) {
          unexpectedServerErrors.push(
            `${response.status()} ${endpoint}`
          );
          console.log(
            `SERVER ERROR DETECTOR: ${username} HTTP ` +
            `${response.status()} ${endpoint}`
          );
        }
      });

      // Log cookie presence only. Never log cookie values or headers.
      page.on('request', async request => {
        const endpoint = new URL(request.url()).pathname;
        if (endpoint !== '/api/visible-msrs/') return;
        const hasCookie = Object.hasOwn(await request.allHeaders(), 'cookie');
        console.log(
          `COOKIE TRACE: ${username} MSR request cookie header ` +
          `${hasCookie ? 'YES' : 'NO'}`
        );
      });

      page.on('response', response => {
        const endpoint = new URL(response.url()).pathname;
        if (
          endpoint === '/api/dev-login/' ||
          endpoint === '/api/me/'
        ) {
          console.log(
            `AUTH TRACE: ${username} ${endpoint} HTTP ${response.status()}`
          );
        }
      });

      // Sequence only; never log cookie contents or credentials.
      let flowSequence = 0;
      const tracedPaths = new Set([
        '/api/dev-login/',
        '/api/me/',
        '/api/activity/',
        '/api/visible-msrs/'
      ]);
      page.on('request', request => {
        const endpoint = new URL(request.url()).pathname;
        if (!tracedPaths.has(endpoint)) return;
        console.log(
          `FLOW TRACE: ${username} ${++flowSequence} START ` +
          `${request.method()} ${endpoint}`
        );
      });
      page.on('response', response => {
        const endpoint = new URL(response.url()).pathname;
        if (!tracedPaths.has(endpoint)) return;
        console.log(
          `FLOW TRACE: ${username} ${++flowSequence} END ` +
          `${response.status()} ${endpoint}`
        );
      });
      page.on('requestfailed', request => {
        const endpoint = new URL(request.url()).pathname;
        if (!tracedPaths.has(endpoint)) return;
        console.log(
          `FLOW TRACE: ${username} ${++flowSequence} NETWORK FAILURE ${endpoint}`
        );
      });

      page.on('response', async response => {
        const endpoint = new URL(response.url()).pathname;
        const expectedEndpoint = regionName === 'Marketing Master Sales Records'
          ? '/api/marketing-msrs/'
          : '/api/visible-msrs/';
        if (endpoint === expectedEndpoint) {
          observed.push(response.status());
        }

        if (
          response.status() === 403 &&
          (endpoint === '/api/visible-msrs/' ||
           endpoint === '/api/activity/')
        ) {
          let category = 'No standard error detail';
          try {
            const body = await response.json();
            const detail = body?.detail;
            if (detail === 'MSR viewing is not authorized.') {
              category = 'MSR role authorization denied';
            } else if (
              typeof detail === 'string' &&
              detail.startsWith('Session expired')
            ) {
              category = 'Session inactivity rejection';
            } else if (
              typeof detail === 'string' &&
              detail.includes('Authentication credentials')
            ) {
              category = 'Missing authentication credentials';
            } else if (
              typeof detail === 'string' &&
              detail.includes('CSRF')
            ) {
              category = 'CSRF validation rejection';
            } else if (typeof detail === 'string') {
              category = 'Other authorization or authentication denial';
            }
          } catch {
            category = 'Non-JSON error response';
          }

          console.log(
            `LIVE BROWSER DIAGNOSTIC: ${username} ` +
            `${endpoint} HTTP 403 - ${category}`
          );
        }
      });

      try {
        await page.goto(
          `${baseURL}/tests/visible-msr/navigation.html`
        );

        await expect(page.getByRole('heading', {
          name: 'Sign in',
        })).toBeVisible();

        await page.getByLabel('Username').fill(username);
        await page.getByLabel('Password').fill(password);

        await page.getByRole('button', {
          name: 'Sign in',
        }).click();

        await expect(page.getByRole('button', {
          name: 'Sign out',
        })).toBeVisible();

        const cookieNames = (await context.cookies(baseURL)).map(
          cookie => cookie.name
        );
        console.log(
          `COOKIE TRACE: ${username} after login session cookie ` +
          `${cookieNames.includes('sessionid') ? 'YES' : 'NO'}`
        );

        const visibleButton = page.getByRole('button', {
          name: buttonName,
          exact: true,
        });

        if (expectedCount === null) {
          await expect(visibleButton).toHaveCount(0);
          console.log(`LIVE BROWSER: ${username} NAVIGATION DENIED`);
          return;
        }

        if (process.env.VERIDIAN_TEST_SERIAL_ACTIVITY === '1') {
          // Test-only: complete one activity request before opening MSRs.
          // The app's 60-second throttle prevents a second immediate ping.
          const activityResult = page.waitForResponse(
            response =>
              new URL(response.url()).pathname === '/api/activity/',
            { timeout: 10000 }
          );
          await page.evaluate(() => {
            window.dispatchEvent(new Event('pointerdown'));
          });
          const completedActivity = await activityResult;
          if (completedActivity.status() !== 200) {
            throw new Error(
              `SERIAL ACTIVITY SAFETY STOP: HTTP ${completedActivity.status()}`
            );
          }
          console.log(
            `SERIAL ACTIVITY: ${username} completed HTTP 200 before MSR click`
          );
        }

        await visibleButton.click();

        await expect(page.getByRole('region', {
          name: regionName,
        })).toBeVisible();

        await expect(page.getByText(
          `${expectedCount} record${expectedCount === 1 ? "" : "s"} available. Page 1.`
        )).toBeVisible();

        if (expectedName !== null) {
          await expect(page.getByRole('heading', {
            name: expectedName,
          })).toBeVisible();
        }

        if (!observed.includes(200)) {
          throw new Error(
            'SAFETY STOP: Expected successful real Django MSR response.'
          );
        }

        await expect(page.getByRole('button', {
          name: 'Create project',
          exact: true,
        })).toHaveCount(0);

        console.log(
          `LIVE BROWSER: ${username} AUTHORIZATION VERIFIED`
        );
      } finally {
        // Flush pending response events before closing this browser context.
        await page.waitForTimeout(250);
        await context.close();

        if (unexpectedServerErrors.length > 0) {
          throw new Error(
            `Unexpected background API server errors for ${username}: ` +
            unexpectedServerErrors.join(', ')
          );
        }
      }
    }

    await verifyRole({
      username: 'http_controller',
      expectedCount: 2,
      expectedName: 'Owned HTTP record',
    });

    await verifyRole({
      username: 'http_sales',
      expectedCount: 1,
      expectedName: 'Owned HTTP record',
    });

    await verifyRole({
      username: 'http_dba',
      expectedCount: null,
    });

    await verifyRole({
      username: 'http_other_sales',
      expectedCount: 1,
      expectedName: 'Other HTTP record',
    });

    await verifyRole({
      username: 'http_ceo',
      expectedCount: 2,
      expectedName: 'Owned HTTP record',
    });

    await verifyRole({
      username: 'http_sales_manager',
      expectedCount: 2,
      expectedName: 'Owned HTTP record',
    });

    await verifyRole({
      username: 'http_installation_manager',
      expectedCount: 2,
      expectedName: 'Owned HTTP record',
    });

    await verifyRole({
      username: 'http_technician',
      expectedCount: 0,
      expectedName: null,
    });

    await verifyRole({
      username: 'http_marketing',
      expectedCount: 2,
      expectedName: 'Owned HTTP record',
      buttonName: 'Master Sales Records',
      regionName: 'Marketing Master Sales Records',
    });

    await verifyRole({
      username: 'http_accounts_payable',
      expectedCount: null,
    });
    console.log('LIVE BROWSER INTEGRATION: PASSED');
  } finally {
    if (browser) await browser.close();
    await vite.close();
    console.log('LIVE BROWSER: ISOLATED VITE SERVER STOPPED');
  }
}

await main();