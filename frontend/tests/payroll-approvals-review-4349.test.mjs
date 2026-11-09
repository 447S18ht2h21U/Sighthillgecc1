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
let Review;
let Workspace;

before(async () => {
  vite = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: { noDiscovery: true, entries: [], include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });

  const reviewModule = await vite.ssrLoadModule(
    '/tests/payroll-approvals-review-4349.tsx'
  );
  const workspaceModule = await vite.ssrLoadModule(
    '/tests/payroll-workspace-approvals-4349.tsx'
  );
  Review = reviewModule.PayrollApprovalsReview4349;
  Workspace = workspaceModule.PayrollWorkspaceApprovals4349;
});

after(async () => {
  if (vite) await vite.close();
});

function fixture() {
  return {
    view: 'fictional_approvals_review_only',
    managerAuthorityVerified: false,
    comptrollerAuthorityVerified: false,
    liveApprovalAuthorized: false,
    rows: [{
      reference: 'TEST-SALES-A',
      recipient: 'Fictional Sales Associate',
      workstream: 'SALES',
      amount: '1250.00',
      requesterId: 'TEST-REQ-A',
      firstApproverId: null,
      finalApproverId: null,
      stage: 'WAITING_MANAGER',
      auditEvidence: 'PENDING',
      actualPaidDate: null,
    }, {
      reference: 'TEST-TECH-B',
      recipient: 'Fictional Technician',
      workstream: 'INSTALLATION',
      amount: '875.00',
      requesterId: 'TEST-REQ-B',
      firstApproverId: 'TEST-MANAGER-B',
      finalApproverId: null,
      stage: 'WAITING_COMPTROLLER',
      auditEvidence: 'PENDING',
      actualPaidDate: null,
    }, {
      reference: 'TEST-SALES-C',
      recipient: 'Fictional Sales Contractor',
      workstream: 'SALES',
      amount: '500.00',
      requesterId: 'TEST-REQ-C',
      firstApproverId: 'TEST-MANAGER-C',
      finalApproverId: 'TEST-COMPTROLLER-C',
      stage: 'APPROVED',
      auditEvidence: 'RECORDED',
      actualPaidDate: null,
    }],
  };
}

function render(data = fixture(), role = 'COMPTROLLER') {
  return renderToStaticMarkup(
    React.createElement(Review, { report: data, role })
  );
}

test('all three approval stages display clearly', () => {
  const html = render();
  assert.match(html, /Awaiting manager review/);
  assert.match(html, /Awaiting Comptroller approval/);
  assert.match(html, /Two approvals recorded/);
});

test('manager and Comptroller approval columns stay separate', () => {
  const html = render();
  assert.match(html, /Manager approval/);
  assert.match(html, /Comptroller approval/);
});

test('approved does not imply paid', () => {
  const html = render();
  assert.match(html, /Approval is not payment/);
  assert.doesNotMatch(html, /Actual payment completed/);
});

test('sales manager sees fictional sales examples only', () => {
  const html = render(fixture(), 'SALES_MANAGER');
  assert.match(html, /Fictional Sales Associate/);
  assert.doesNotMatch(html, /Fictional Technician/);
});

test('installation manager sees fictional installation examples only', () => {
  const html = render(fixture(), 'INSTALLATION_MANAGER');
  assert.match(html, /Fictional Technician/);
  assert.doesNotMatch(html, /Fictional Sales Associate/);
});

test('personal-only positions cannot render approvals review', () => {
  assert.throws(() => render(fixture(), 'TECHNICIAN'));
  assert.throws(() => render(fixture(), 'SALES_ASSOCIATE'));
});

test('self-approval is rejected', () => {
  const data = fixture();
  data.rows[1].firstApproverId = 'TEST-REQ-B';
  assert.throws(() => render(data));
});

test('same individual cannot perform both approvals', () => {
  const data = fixture();
  data.rows[2].finalApproverId = 'TEST-MANAGER-C';
  assert.throws(() => render(data));
});

test('Comptroller approval without first approver is rejected', () => {
  const data = fixture();
  data.rows[2].firstApproverId = null;
  assert.throws(() => render(data));
});

test('missing recorded audit evidence rejects final approval', () => {
  const data = fixture();
  data.rows[2].auditEvidence = 'PENDING';
  assert.throws(() => render(data));
});

test('verified authority claims and paid dates are rejected', () => {
  const data = fixture();
  data.managerAuthorityVerified = true;
  assert.throws(() => render(data));

  const second = fixture();
  second.rows[2].actualPaidDate = '2026-11-11';
  assert.throws(() => render(second));
});

test('approvals component is isolated within workspace tab', () => {
  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-workspace-approvals-4349.tsx'),
    'utf8'
  );
  const start = source.indexOf("activeTab === 'Approvals'");
  const end = source.indexOf("activeTab === 'Payment History'");
  assert.ok(start > 0 && end > start);
  assert.match(source.slice(start, end), /PayrollApprovalsReview4349/);

  const workspaceHtml = renderToStaticMarkup(
    React.createElement(Workspace, { role: 'COMPTROLLER' })
  );
  assert.match(workspaceHtml, /My Payroll/);
  assert.match(workspaceHtml, /Weekly Payroll/);
  assert.match(workspaceHtml, /Contractor Records/);
  assert.doesNotMatch(workspaceHtml, /Fictional Sales Associate/);

  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollWorkspaceApprovals4349/);
  assert.doesNotMatch(routes, /payroll_approvals_review_4349/);
  assert.doesNotMatch(render(), /<form\b/);
});