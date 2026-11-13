import { existsSync, writeFileSync, unlinkSync } from 'node:fs';
import { resolve } from 'node:path';
import { createServer } from 'vite';
import { chromium } from '@playwright/test';

const root = process.cwd();
const html = resolve(root, 'ruud-acceptance-4653.html');
const fixture = resolve(root, 'src/ruud-acceptance-4653.tsx');

if (existsSync(html) || existsSync(fixture)) {
  throw new Error('SAFETY STOP: Temporary fixture already exists.');
}

const htmlSource = `<!doctype html>
<html lang="en">
<head><meta charset="UTF-8"/></head>
<body>
<div id="root"></div>
<script type="module" src="/src/ruud-acceptance-4653.tsx"></script>
</body>
</html>`;

const fixtureSource = `
import React from 'react';
import { createRoot } from 'react-dom/client';
import { NamedProductCatalog4547 } from './NamedProductCatalog4547';
import './style.css';

const mode = new URLSearchParams(location.search).get('mode');
const importPath = 'development-product-catalogs/import-ruud-2026/';
const catalogPath = 'development-product-catalogs/';
const catalogId = 'ruud-browser-fixture';
let imported = false;
let requests = 0;

type Catalog = {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
};

const catalog: Catalog = {
  id: catalogId,
  name: 'Ruud Residential Systems',
  description: 'Isolated browser acceptance fixture',
  is_active: true,
};

const products = Array.from({length: 15}, (_, index) => ({
  id: 'fixture-equipment-' + (index + 1),
  brand: 'Ruud',
  residential_system_type: 'A/C and Furnace',
  model_number: 'BROWSER-FIXTURE-' + (index + 1),
  description: 'Isolated interface verification only',
  revision: 1,
  is_active: true,
}));

async function api<T>(
  path: string,
  method = 'GET',
  _data?: unknown,
): Promise<T> {
  if (path === importPath) {
    if (method === 'GET') {
      if (mode === 'error') {
        throw new Error('Synthetic readiness failure');
      }
      return {
        available: mode === 'ready',
        catalog: 'Ruud Residential Systems',
        system_count: 15,
        persistent_activation: false,
        reason: mode === 'ready'
          ? 'Isolated development catalog import is available.'
          : 'Catalog database activation is pending. Persistent imports are disabled.',
      } as T;
    }
    if (method === 'POST') {
      requests += 1;
      if (mode !== 'ready') {
        throw new Error('SAFETY STOP: Import attempted while blocked.');
      }
      const added = imported ? 0 : 15;
      imported = true;
      return {
        catalog_id: catalogId,
        catalog_name: catalog.name,
        added,
        total: 15,
        status: added ? 'IMPORTED' : 'ALREADY_PRESENT',
        persistent_activation: false,
      } as T;
    }
  }

  if (path === catalogPath && method === 'GET') {
    return (imported ? [catalog] : []) as T;
  }

  if (path === catalogPath + catalogId + '/products/' &&
      method === 'GET') {
    return (imported ? products : []) as T;
  }

  throw new Error('Unexpected mock API operation: ' + method + ' ' + path);
}

Object.assign(window, {
  ruudFixtureState: () => ({requests, imported}),
});

createRoot(document.getElementById('root')!).render(
  <NamedProductCatalog4547 api={api}/>
);
`;

let server;
let browser;
let failure;

try {
  writeFileSync(html, htmlSource, {flag: 'wx'});
  writeFileSync(fixture, fixtureSource, {flag: 'wx'});

  server = await createServer({
    server: {
      host: '127.0.0.1',
      port: 0,
      strictPort: false,
    },
    logLevel: 'error',
  });

  await server.listen();

  const address = server.httpServer?.address();

  if (!address || typeof address === 'string') {
    throw new Error('Unable to verify local Vite listening port.');
  }

  const base = 'http://127.0.0.1:' + address.port;
  const chrome = process.env.GECC_BROWSER_EXECUTABLE;

  browser = await chromium.launch({
    executablePath: chrome,
    headless: true,
  });

  const page = await browser.newPage();
  const errors = [];

  page.on('pageerror', error => errors.push(error.message));

  async function open(mode) {
    await page.goto(base + '/ruud-acceptance-4653.html?mode=' + mode);
    await page.getByRole('heading', {
      name: 'Ruud Residential Systems — 2026',
    }).waitFor();
  }

  const button = page.getByRole('button', {
    name: 'Import 15 Ruud Systems',
  });

  // Scenario 1: persistent database is not activated.
  await open('blocked');
  await page.getByText(
    'Catalog database activation is pending.',
    {exact: false},
  ).waitFor();

  if (await button.isEnabled()) {
    throw new Error('FAIL: Blocked import button is enabled.');
  }

  console.log('PASS: Persistent catalog import remains disabled.');

  // Scenario 2: API readiness cannot be verified.
  await open('error');
  await page.getByText(
    'Ruud import readiness could not be verified.',
  ).waitFor();

  if (await button.isEnabled()) {
    throw new Error('FAIL: Readiness failure enabled import.');
  }

  console.log('PASS: Readiness errors fail closed.');

  // Scenario 3: isolated, permitted import through the interface.
  await open('ready');
  await page.getByText(
    'Isolated development catalog import is available.',
  ).waitFor();

  if (!(await button.isEnabled())) {
    throw new Error('FAIL: Authorized isolated import not enabled.');
  }

  await button.click();

  await page.getByText(
    'All 15 Ruud systems imported with audit history.',
  ).waitFor();

  await page.getByRole('heading', {
    name: 'Catalog Products (15)',
  }).waitFor();

  const selectedCatalog = page.locator('section[aria-label="Named product catalogs"] select').first();

  if ((await selectedCatalog.inputValue()) !== 'ruud-browser-fixture') {
    throw new Error('FAIL: Imported catalog was not selected.');
  }

  const productCount = await page.locator(
    '.line strong',
  ).filter({hasText: 'Ruud'}).count();

  if (productCount !== 15) {
    throw new Error(
      'FAIL: Expected 15 displayed Ruud products, got ' + productCount,
    );
  }

  const state = await page.evaluate(() =>
    window.ruudFixtureState(),
  );

  if (state.requests !== 1 || !state.imported) {
    throw new Error('FAIL: Unexpected browser import request count.');
  }

  if (errors.length) {
    throw new Error('Browser JavaScript errors: ' + errors.join('; '));
  }

  console.log('PASS: Authorized import action submitted exactly once.');
  console.log('PASS: Catalog refreshed and selected after import.');
  console.log('PASS: All 15 simulated product rows displayed.');
  console.log('PASS: No browser JavaScript errors.');
  console.log('=== RUUD CHROME ACCEPTANCE: PASSED ===');
} catch (error) {
  failure = error;
  console.error('SAFETY STOP:', error.message);
} finally {
  if (browser) await browser.close();
  if (server) await server.close();

  if (existsSync(fixture)) unlinkSync(fixture);
  if (existsSync(html)) unlinkSync(html);

  console.log('Temporary browser fixtures: REMOVED');
  console.log('Persistent database writes: NONE');
}

if (failure) process.exitCode = 1;
