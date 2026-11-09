import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { createServer } from 'vite';
import { readFileSync } from 'node:fs';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(frontend, '..');
const require = createRequire(resolve(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

let vite;
let Register;

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
    '/tests/payroll-weekly-register-4344.tsx'
  );
  Register = module.PayrollWeeklyRegister4344;
  assert.equal(typeof Register, 'function');
});

after(async () => {
  if (vite) await vite.close();
});

function fixture() {
  return {
    view: 'fictional_weekly_register_only',
    historicalRoleBindingVerified: false,
    managerAccessAuthorized: false,
    livePayrollAuthorized: false,
    rows: [
      {
        reference: 'TEST-A',
        recipient: 'Fictional Contractor A',
        category: 'contractor',
        periodStart: '2026-11-02',
        periodEnd: '2026-11-08',
        amount: '1250.00',
        managerApproval: 'PENDING',
        comptrollerApproval: 'PENDING',
        scheduledDate: null,
        recordedStatus: 'DRAFT',
        actualPaidDate: null,
        actualPaidDateVerified: false,
        exception: false,
      },
      {
        reference: 'TEST-B',
        recipient: 'Fictional Contractor B',
        category: 'contractor',
        periodStart: '2026-11-02',
        periodEnd: '2026-11-08',
        amount: '875.00',
        managerApproval: 'APPROVED',
        comptrollerApproval: 'PENDING',
        scheduledDate: '2026-11-11',
        recordedStatus: 'DRAFT',
        actualPaidDate: null,
        actualPaidDateVerified: false,
        exception: true,
      },
    ],
  };
}

function render(data = fixture()) {
  return renderToStaticMarkup(
    React.createElement(Register, { report: data })
  );
}

test('fictional weekly amounts are displayed accurately', () => {
  const html = render();
  assert.match(html, /\$1,250\.00/);
  assert.match(html, /\$875\.00/);
});

test('Monday Sunday period is displayed', () => {
  const html = render();
  assert.match(html, /2026-11-02 to 2026-11-08/);
});

test('scheduled Wednesday is distinct from actual paid date', () => {
  const html = render();
  assert.match(html, /2026-11-11/);
  assert.match(html, /Not independently established/);
});

test('manager and Comptroller approvals are separate', () => {
  const html = render();
  assert.match(html, /Manager approval/);
  assert.match(html, /Comptroller approval/);
  assert.match(html, /Recorded approved/);
  assert.match(html, /Pending/);
});

test('exceptions are visible without authorizing payment', () => {
  const html = render();
  assert.match(html, /Review required/);
  assert.match(html, /No live payroll actions or exports/);
});

test('unverified manager authorization is always denied', () => {
  const data = fixture();
  data.managerAccessAuthorized = true;
  assert.throws(() => render(data));
  data.managerAccessAuthorized = false;
  data.historicalRoleBindingVerified = true;
  assert.throws(() => render(data));
});

test('conflicting approval states fail closed', () => {
  const data = fixture();
  data.rows[0].comptrollerApproval = 'APPROVED';
  assert.throws(() => render(data));
});

test('incorrect Wednesday and invented paid date fail closed', () => {
  const data = fixture();
  data.rows[1].scheduledDate = '2026-11-12';
  assert.throws(() => render(data));

  const second = fixture();
  second.rows[0].actualPaidDate = '2026-11-11';
  assert.throws(() => render(second));
});

test('invalid status or unsafe payroll amount fails closed', () => {
  const data = fixture();
  data.rows[0].recordedStatus = 'PAID';
  assert.throws(() => render(data));

  const second = fixture();
  second.rows[0].amount = '-50.00';
  assert.throws(() => render(second));
});

test('weekly register remains outside live payroll routes', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollWeeklyRegister4344/);
  assert.doesNotMatch(urls, /payroll_weekly_register_4344/);
  assert.doesNotMatch(render(), /<form\b/);
});