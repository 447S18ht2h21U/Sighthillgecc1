import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
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
    '/tests/payroll-workspace-tab-4338.tsx'
  );
  Workspace = mod.PayrollWorkspaceTab4338;

  const python = resolve(root, '.venv', 'Scripts', 'python.exe');
  const fixture = resolve(
    root, 'backend', 'core', 'payroll_contract_fixture_4333.py'
  );

  const result = spawnSync(python, [fixture, 'valid'], {
    cwd: root,
    encoding: 'utf8',
    timeout: 15000,
    env: {
      ...process.env,
      DJANGO_SETTINGS_MODULE: 'core.test_document_db_settings_4243',
      GECC_DEV: '1',
      VERIDIAN_ENVIRONMENT: 'development',
      VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED: 'False',
    },
  });

  assert.equal(result.status, 0, result.stderr);
  report = mapAuthorizedPersonalPayroll4332(
    JSON.parse(result.stdout)
  );
});

after(async () => {
  if (vite) await vite.close();
});

function page(role = 'COMPTROLLER', data = report) {
  return renderToStaticMarkup(
    React.createElement(Workspace, { role, report: data })
  );
}

test('backend-mapped records appear inside My Payroll tab', () => {
  const html = page();
  assert.match(html, /aria-label="My Payroll"/);
  assert.match(html, /aria-label="Test-only personal payroll records"/);
  assert.match(html, /\$600\.00/);
  assert.match(html, /\$1,250\.00/);
});

test('personal payroll records are not rendered below workspace', () => {
  const html = page();
  const first = html.indexOf(
    'aria-label="Test-only personal payroll records"'
  );
  const footer = html.indexOf(
    'Every Record. Every Decision. Every Step.'
  );
  assert.ok(first > 0 && first < footer);
  assert.equal(
    (html.match(/aria-label="Test-only personal payroll records"/g) || [])
      .length,
    1
  );
});

test('approved six payroll tabs remain intact for Comptroller', () => {
  const html = page();
  for (const tab of [
    'My Payroll', 'Weekly Payroll', 'Approvals',
    'Payment History', 'Contractor Records', 'Reports',
  ]) {
    assert.ok(html.includes(tab), tab);
  }
});

test('personal-only roles have no management tabs', () => {
  for (const role of ['SALES_ASSOCIATE', 'TECHNICIAN']) {
    const html = page(role);
    assert.doesNotMatch(html, />Weekly Payroll</);
    assert.doesNotMatch(html, />Approvals</);
    assert.doesNotMatch(html, />Contractor Records</);
    assert.match(html, /\$600\.00/);
  }
});

test('paid status does not invent verified payment dates', () => {
  const html = page();
  assert.match(html, /Approved - Not Yet Paid/);
  assert.match(html, /Not independently established/);
  assert.doesNotMatch(html, /2026-11-12/);
});

test('unsafe payroll contract fails before rendering records', () => {
  assert.throws(() => page('COMPTROLLER', {
    ...report,
    paymentActionsAvailable: true,
  }));
  assert.throws(() => page('COMPTROLLER', {
    ...report,
    livePayrollAuthorized: true,
  }));
});

test('approved workspace still shows fictional placeholder without data', () => {
  const html = page('COMPTROLLER', null);
  assert.match(html, /Your individual earnings/);
});

test('test-only integration stays out of live navigation', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceTab4338/);
  assert.doesNotMatch(routes, /payroll_workspace_tab_4338/);
  assert.match(page(), /Development preview only/);
});