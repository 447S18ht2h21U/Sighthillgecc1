import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { createServer } from 'vite';

import {
  mapAuthorizedPersonalPayroll4332,
} from './payroll-personal-screen-mapper-4332.mjs';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(frontend, '..');

const require = createRequire(resolve(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

let vite;
let Workspace;
let report;

before(async () => {
  vite = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: {
      noDiscovery: true,
      entries: [],
      include: [],
    },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });

  const mod = await vite.ssrLoadModule(
    '/tests/payroll-workspace-tab-4341.tsx'
  );
  Workspace = mod.PayrollWorkspaceTab4341;

  const json = JSON.parse(readFileSync(
    resolve(frontend, 'tests', 'payroll-synthetic-report-4339.json'),
    'utf8'
  ));
  report = mapAuthorizedPersonalPayroll4332(json);
});

after(async () => {
  if (vite) await vite.close();
});

function page(role = 'COMPTROLLER', data = report) {
  return renderToStaticMarkup(
    React.createElement(Workspace, { role, report: data })
  );
}

test('My Payroll has only one visible heading', () => {
  const html = page();
  assert.equal(
    (html.match(/<h2>My Payroll<\/h2>/g) || []).length,
    1
  );
});

test('payroll records appear inside the approved tab', () => {
  const html = page();
  assert.match(html, /aria-label="My Payroll"/);
  assert.match(html, /Test-only personal payroll records/);
  assert.match(html, /\$600\.00/);
  assert.match(html, /\$1,250\.00/);
});

test('no second bordered personal payroll panel exists', () => {
  const html = page();
  assert.equal(
    (html.match(/data-test-only="true"/g) || []).length,
    1
  );
  assert.doesNotMatch(
    html,
    /<section[^>]+aria-label="Test-only personal payroll records"/
  );
});

test('technical evidence codes are not displayed', () => {
  const html = page();
  assert.match(html, /Not issued/);
  assert.match(html, /Verification pending/);
  assert.doesNotMatch(html, /NOT_ISSUED|TEST_ONLY_UNVERIFIED/);
});

test('Paid status does not claim a verified disbursement', () => {
  const html = page();
  assert.match(html, /Recorded as Paid - actual date not verified/);
  assert.match(html, /Not independently established/);
  assert.doesNotMatch(html, /2026-11-12/);
});

test('all six management tabs are preserved', () => {
  const html = page();
  for (const name of [
    'My Payroll', 'Weekly Payroll', 'Approvals',
    'Payment History', 'Contractor Records', 'Reports',
  ]) {
    assert.ok(html.includes(name), name);
  }
});

test('personal roles do not gain management tabs', () => {
  const html = page('TECHNICIAN');
  assert.doesNotMatch(html, />Weekly Payroll</);
  assert.doesNotMatch(html, />Approvals</);
  assert.doesNotMatch(html, />Contractor Records</);
});

test('unsafe flags fail and operational navigation stays unchanged', () => {
  assert.throws(() => page('COMPTROLLER', {
    ...report,
    paymentActionsAvailable: true,
  }));

  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceTab4341/);
  assert.doesNotMatch(urls, /payroll_workspace_tab_4341/);
  assert.match(page(), /Development preview only/);
});