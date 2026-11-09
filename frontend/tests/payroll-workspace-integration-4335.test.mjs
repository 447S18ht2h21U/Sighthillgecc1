import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
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
  const module = await vite.ssrLoadModule(
    '/tests/payroll-workspace-integration-4335.tsx'
  );
  Workspace = module.PayrollWorkspaceIntegration4335;
  assert.equal(typeof Workspace, 'function');
});

after(async () => {
  if (vite) await vite.close();
});

function report() {
  const python = resolve(root, '.venv', 'Scripts', 'python.exe');
  const script = resolve(
    root, 'backend', 'core', 'payroll_contract_fixture_4333.py'
  );

  const result = spawnSync(python, [script, 'valid'], {
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
  return mapAuthorizedPersonalPayroll4332(JSON.parse(result.stdout));
}

let sample;
function page(role = 'COMPTROLLER', data = sample) {
  return renderToStaticMarkup(
    React.createElement(Workspace, { role, report: data })
  );
}

test('Python contract and approved workspace compose together', () => {
  sample = report();
  const html = page();
  assert.match(html, /data-payroll-integration="isolated-test-only"/);
  assert.match(html, /Payroll/);
});

test('Comptroller preview retains six approved tabs', () => {
  const html = page('COMPTROLLER');
  for (const name of [
    'My Payroll', 'Weekly Payroll', 'Approvals',
    'Payment History', 'Contractor Records', 'Reports',
  ]) {
    assert.ok(html.includes(name), name);
  }
});

test('Sales associate preview has no management tabs', () => {
  const html = page('SALES_ASSOCIATE');
  assert.doesNotMatch(html, />Weekly Payroll</);
  assert.doesNotMatch(html, />Contractor Records</);
});

test('Technician preview has no approval or contractor tabs', () => {
  const html = page('TECHNICIAN');
  assert.doesNotMatch(html, />Approvals</);
  assert.doesNotMatch(html, />Contractor Records</);
});

test('Mapped backend compensation values render accurately', () => {
  const html = page();
  assert.match(html, /\$600\.00/);
  assert.match(html, /\$1,250\.00/);
  assert.match(html, /Approved - Not Yet Paid/);
});

test('Actual paid date is never invented by integration', () => {
  const html = page();
  assert.match(html, /Not independently established/);
  assert.doesNotMatch(html, /2026-11-12/);
});

test('Unsafe action flags are rejected before rendering', () => {
  assert.throws(() => page('COMPTROLLER', {
    ...sample,
    paymentActionsAvailable: true,
  }));
  assert.throws(() => page('COMPTROLLER', {
    ...sample,
    livePayrollAuthorized: true,
  }));
});

test('Composition remains test-only and outside live routing', () => {
  const html = page();
  assert.match(html, /Synthetic contract verification only/);
  assert.doesNotMatch(html, /<form\b/);

  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceIntegration4335/);
  assert.doesNotMatch(routes, /payroll_workspace_integration_4335/);
});