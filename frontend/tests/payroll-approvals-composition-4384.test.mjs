import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { build } from 'esbuild';

const require = createRequire(import.meta.url);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const compiled = await build({
  entryPoints: [
    resolve('tests/payroll-approvals-composition-4384.tsx')
  ],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  packages: 'external',
  write: false,
  logLevel: 'silent',
});

const module = { exports: {} };
new Function(
  'require', 'module', 'exports',
  compiled.outputFiles[0].text
)(require, module, module.exports);

const Composition = module.exports.PayrollApprovalsComposition4384;
assert.equal(typeof Composition, 'function');

function fixture() {
  return {
    view: 'fictional_approvals_review_only',
    manager_authority_verified: false,
    comptroller_authority_verified: false,
    live_approval_authorized: false,
    payment_actions_authorized: false,
    actual_paid_date_verified: false,
    rows: [
      {
        reference: 'TEST-SALES',
        recipient: 'Fictional Sales Associate',
        workstream: 'SALES',
        amount: '1250.00',
        requester_id: 'TEST-REQUESTER-A',
        first_approver_id: null,
        final_approver_id: null,
        stage: 'WAITING_MANAGER',
        audit_evidence: 'PENDING',
        actual_paid_date: null,
        actual_paid_date_verified: false,
      },
      {
        reference: 'TEST-TECH',
        recipient: 'Fictional Technician',
        workstream: 'INSTALLATION',
        amount: '875.00',
        requester_id: 'TEST-REQUESTER-B',
        first_approver_id: 'TEST-MANAGER',
        final_approver_id: null,
        stage: 'WAITING_COMPTROLLER',
        audit_evidence: 'PENDING',
        actual_paid_date: null,
        actual_paid_date_verified: false,
      },
    ],
  };
}

function render(data, role = 'CEO') {
  return renderToStaticMarkup(
    React.createElement(Composition, {
      fictionalSource: data,
      role,
    })
  );
}

test('01 translated records render in approved review', () => {
  const html = render(fixture());
  assert.match(html, /Fictional Sales Associate/);
  assert.match(html, /Fictional Technician/);
  assert.match(html, /Awaiting manager review/);
  assert.match(html, /Awaiting Comptroller approval/);
  assert.match(html, /Manager approval/);
  assert.match(html, /Comptroller approval/);
});

test('02 fictional role display remains workstream-specific', () => {
  const sales = render(fixture(), 'SALES_MANAGER');
  assert.match(sales, /Fictional Sales Associate/);
  assert.doesNotMatch(sales, /Fictional Technician/);

  const installation = render(fixture(), 'INSTALLATION_MANAGER');
  assert.match(installation, /Fictional Technician/);
  assert.doesNotMatch(installation, /Fictional Sales Associate/);
});

test('03 unsafe input fails before React can display it', () => {
  const self = fixture();
  self.rows[0].first_approver_id = 'TEST-REQUESTER-A';
  assert.throws(() => render(self));

  const elevated = fixture();
  elevated.live_approval_authorized = true;
  assert.throws(() => render(elevated));

  assert.throws(() => render(fixture(), 'TECHNICIAN'));
});

test('04 sensitive data and payment controls remain excluded', () => {
  const data = fixture();
  data.rows[0].bank_account = 'SECRET-DO-NOT-EXPOSE';
  data.company_total = '999999.00';

  const html = render(data);
  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /999999/);
  assert.match(html, /Approval is not payment/);
  assert.match(html, /Fictional approval review only/);
  assert.doesNotMatch(html, /<button/i);
});
