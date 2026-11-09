import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
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
    optimizeDeps: { noDiscovery: true, entries: [], include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  const loaded = await vite.ssrLoadModule(
    '/tests/payroll-personal-workspace-4374.tsx'
  );
  Workspace = loaded.PayrollPersonalWorkspace4374;
});

after(async () => {
  if (vite) await vite.close();
});

function payload() {
  const employee = {
    compensation_type: 'employee',
    period_start: '2026-11-02',
    period_end: '2026-11-08',
    kind: 'Fictional compensation',
    amount: '600.00',
    status: 'APPROVED',
    status_label: 'Approved - Not Yet Paid',
    payment_evidence_status: 'NOT_ISSUED',
    scheduled_payment_date: null,
    actual_paid_date: null,
    actual_paid_date_verified: false,
  };
  return {
    view: 'my_payroll_test_only',
    amount_basis: 'full_obligation_not_prorated',
    period_start: '2026-11-02',
    period_end: '2026-11-08',
    employee_records: [employee],
    contractor_records: [{
      ...employee,
      compensation_type: 'contractor',
      amount: '1250.00',
      status: 'PAID',
      status_label: 'Paid',
      payment_evidence_status: 'TEST_ONLY_UNVERIFIED',
    }],
    manager_or_company_scope_authorized: false,
    payment_actions_authorized: false,
    actual_paid_date_verified: false,
    live_payroll_authorized: false,
  };
}

function props(overrides = {}) {
  return {
    role: 'COMPTROLLER',
    authorizedPersonalPayload: payload(),
    onReturnToProjects: () => {},
    ...overrides,
  };
}

function page(overrides = {}) {
  return renderToStaticMarkup(React.createElement(Workspace, props(overrides)));
}

function navigation(html) {
  const match = html.match(/<nav\b[^>]*aria-label="Payroll sections"[^>]*>([\s\S]*?)<\/nav>/);
  assert.ok(match, 'Approved payroll navigation must exist');
  return match[1];
}

test('mapped records stay inside My Payroll with the approved navigation', () => {
  const html = page();
  const section = html.match(/<section\b[^>]*aria-label="My Payroll"[^>]*>([\s\S]*?)<\/section>/);
  assert.ok(section, 'My Payroll section must exist');
  assert.match(section[1], />600\.00</);
  assert.match(section[1], />1250\.00</);
  assert.match(section[1], /Approved - Not Yet Paid/);
  assert.match(section[1], /Recorded as Paid - actual date not verified/);
  assert.match(section[1], /Not independently established/);
  assert.doesNotMatch(html.replace(section[0], ''), /600\.00|1250\.00/);
  assert.equal((html.match(/<h2>My Payroll<\/h2>/g) || []).length, 1);

  const nav = navigation(html);
  const buttons = [...nav.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)];
  assert.deepEqual(buttons.map(match => match[1]), [
    'My Payroll', 'Weekly Payroll', 'Approvals', 'Payment History',
    'Contractor Records', 'Reports', 'Return to Customers &amp; Projects',
  ]);
  assert.match(buttons[6][0], /margin-left:auto/);
});

test('personal preview roles retain restricted tabs after composition', () => {
  for (const role of ['SALES_ASSOCIATE', 'TECHNICIAN']) {
    const nav = navigation(page({ role }));
    assert.match(nav, />My Payroll</);
    assert.match(nav, />Payment History</);
    assert.match(nav, />Reports</);
    assert.doesNotMatch(nav, />Weekly Payroll<|>Approvals<|>Contractor Records</);
  }
});

test('unsafe source contracts stop rendering at the connected boundary', () => {
  const scope = payload();
  scope.manager_or_company_scope_authorized = true;
  assert.throws(() => page({ authorizedPersonalPayload: scope }));

  const dated = payload();
  dated.contractor_records[0].actual_paid_date = '2026-11-12';
  assert.throws(() => page({ authorizedPersonalPayload: dated }));

  assert.throws(() => page({ authorizedPersonalPayload: undefined }));
});

test('private source fields and a supplied mapped report cannot bypass translation', () => {
  const source = payload();
  source.employee_records[0].private_identifier = 'PRIVATE-SOURCE-4374';
  source.private_notes = 'PRIVATE-NOTES-4374';
  const html = page({
    authorizedPersonalPayload: source,
    report: {
      view: 'UNSAFE-BYPASS-4374',
      employeeRecords: [{ amount: 'UNSAFE-BYPASS-4374' }],
    },
  });
  assert.match(html, />600\.00</);
  assert.doesNotMatch(html, /PRIVATE-SOURCE-4374|PRIVATE-NOTES-4374|UNSAFE-BYPASS-4374/);
});

test('host return callback remains connected and required', () => {
  let calls = 0;
  const onReturnToProjects = () => { calls += 1; };
  const element = Workspace(props({ onReturnToProjects }));
  assert.equal(calls, 0);
  assert.equal(element.props.onReturnToProjects, onReturnToProjects);
  element.props.onReturnToProjects();
  assert.equal(calls, 1);
  assert.throws(() => page({ onReturnToProjects: undefined }));
});