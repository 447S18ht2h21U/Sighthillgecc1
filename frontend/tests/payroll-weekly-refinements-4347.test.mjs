import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { createServer } from 'vite';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(frontend, '..');
const require = createRequire(resolve(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

let vite;
let Register;
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

  const registerModule = await vite.ssrLoadModule(
    '/tests/payroll-weekly-register-4347.tsx'
  );
  const workspaceModule = await vite.ssrLoadModule(
    '/tests/payroll-workspace-weekly-4347.tsx'
  );

  Register = registerModule.PayrollWeeklyRegister4347;
  Workspace = workspaceModule.PayrollWorkspaceWeekly4347;

  assert.equal(typeof Register, 'function');
  assert.equal(typeof Workspace, 'function');
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
    rows: [{
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
    }, {
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
    }],
  };
}

function render(data = fixture()) {
  return renderToStaticMarkup(
    React.createElement(Register, { report: data })
  );
}

test('table has a readable minimum width', () => {
  const html = render();
  assert.match(html, /min-width:1450px/);
});

test('narrow screens retain horizontal scrolling', () => {
  const html = render();
  assert.match(html, /overflow-x:auto/);
});

test('payment periods remain legible without wrapping', () => {
  const html = render();
  assert.match(html, /white-space:nowrap/);
  assert.match(html, /2026-11-02 to 2026-11-08/);
});

test('Manager and Comptroller columns remain separate', () => {
  const html = render();
  assert.match(html, /Manager approval/);
  assert.match(html, /Comptroller approval/);
});

test('approval wording is clear and concise', () => {
  const html = render();
  assert.match(html, /Approved/);
  assert.match(html, /Pending/);
  assert.doesNotMatch(html, /Recorded approved/);
});

test('Wednesday with pending Comptroller approval is proposed', () => {
  const html = render();
  assert.match(html, /Proposed: 2026-11-11/);
  assert.doesNotMatch(html, /Scheduled: 2026-11-11/);
});

test('fully approved record may display scheduled Wednesday', () => {
  const data = fixture();
  data.rows[1].comptrollerApproval = 'APPROVED';
  data.rows[1].recordedStatus = 'APPROVED';
  const html = render(data);
  assert.match(html, /Scheduled: 2026-11-11/);
});

test('an unapproved draft never claims a formal schedule', () => {
  const data = fixture();
  data.rows[1].comptrollerApproval = 'APPROVED';
  data.rows[1].recordedStatus = 'DRAFT';
  assert.match(render(data), /Proposed: 2026-11-11/);
});

test('unverified actual payment dates still fail closed', () => {
  const data = fixture();
  data.rows[0].actualPaidDate = '2026-11-11';
  assert.throws(() => render(data));
});

test('unauthorized manager access claims still fail closed', () => {
  const data = fixture();
  data.managerAccessAuthorized = true;
  assert.throws(() => render(data));
});

test('combined workspace retains approved tabs and presentation', () => {
  const html = renderToStaticMarkup(
    React.createElement(Workspace, { role: 'COMPTROLLER' })
  );
  assert.match(html, /My Payroll/);
  assert.match(html, /Weekly Payroll/);
  assert.match(html, /Approvals/);
  assert.match(html, /Contractor Records/);
  assert.match(html, /Reports/);

  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-workspace-weekly-4347.tsx'),
    'utf8'
  );

  assert.match(source, /PayrollWeeklyRegister4347/);
});

test('live navigation and backend registration remain untouched', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceWeekly4347/);
  assert.doesNotMatch(routes, /payroll_weekly_register_4347/);
  assert.doesNotMatch(render(), /<form\b/);
});