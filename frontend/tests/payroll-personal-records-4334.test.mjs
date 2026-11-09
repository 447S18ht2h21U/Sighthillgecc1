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
let Component;

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
    '/tests/payroll-personal-records-4334.tsx'
  );
  Component = module.PayrollPersonalRecords4334;
  assert.equal(typeof Component, 'function');
});

after(async () => {
  if (vite) await vite.close();
});

function pythonFixture(caseName = 'valid') {
  const python = resolve(root, '.venv', 'Scripts', 'python.exe');
  const script = resolve(
    root, 'backend', 'core', 'payroll_contract_fixture_4333.py'
  );

  const result = spawnSync(python, [script, caseName], {
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
  return JSON.parse(result.stdout);
}

function render(report) {
  return renderToStaticMarkup(
    React.createElement(Component, { report })
  );
}

function mapped() {
  return mapAuthorizedPersonalPayroll4332(pythonFixture());
}

test('real Python formatter output renders in isolated React', () => {
  const html = render(mapped());
  assert.match(html, /My Payroll/);
  assert.match(html, /data-test-only="true"/);
});

test('employee and contractor amounts retain exact cents', () => {
  const html = render(mapped());
  assert.match(html, /\$600\.00/);
  assert.match(html, /\$1,250\.00/);
});

test('React preserves approved-versus-paid distinctions', () => {
  const html = render(mapped());
  assert.match(html, /Approved - Not Yet Paid/);
  assert.match(html, />Paid</);
});

test('pay periods remain consistent with Python evidence', () => {
  const html = render(mapped());
  assert.match(html, /2026-11-02/);
  assert.match(html, /2026-11-08/);
});

test('no verified actual payment date is invented', () => {
  const html = render(mapped());
  assert.match(html, /Not independently established/);
  assert.doesNotMatch(html, /2026-11-12/);
});

test('private fields cannot reach the rendered page', () => {
  const report = mapAuthorizedPersonalPayroll4332(
    pythonFixture('private_fields')
  );
  const html = render(report);
  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
});

test('malformed or unauthorized scope cannot render', () => {
  const report = mapped();
  assert.throws(
    () => render({ ...report, livePayrollAuthorized: true })
  );
  assert.throws(
    () => render({ ...report, paymentActionsAvailable: true })
  );
});

test('rendered component never activates operational payroll', () => {
  const html = render(mapped());
  assert.doesNotMatch(html, /<form\b/);
  assert.doesNotMatch(html, /type="submit"/);
  assert.match(html, /report exports are disabled/);

  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollPersonalRecords4334/);
  assert.doesNotMatch(routes, /payroll_personal_records_4334/);
});