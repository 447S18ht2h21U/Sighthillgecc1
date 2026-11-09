import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
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

const loaded = { exports: {} };
new Function(
  'require', 'module', 'exports',
  compiled.outputFiles[0].text
)(require, loaded, loaded.exports);

const Component = loaded.exports.PayrollApprovalsComposition4384;

assert.equal(typeof Component, 'function');

const pythonSource = `
import json
import os
import sys

sys.path.insert(0, os.environ["VERIDIAN_BACKEND_CORE"])

from payroll_approval_screen_4389 import (
    format_fictional_approval_screen_4389,
)

def row(ref, recipient, workstream, stage):
    data = {
        "reference": ref,
        "recipient": recipient,
        "workstream": workstream,
        "amount": "1250.00",
        "requester_id": "TEST-REQUESTER",
        "recipient_id": "TEST-RECIPIENT",
        "first_approver_id": None,
        "first_approver_role": None,
        "first_audit_reference": None,
        "final_approver_id": None,
        "final_approver_role": None,
        "final_audit_reference": None,
        "stage": stage,
        "audit_evidence": "PENDING",
        "actual_paid_date": None,
        "actual_paid_date_verified": False,
        "bank_account": "SECRET-DO-NOT-EXPOSE",
    }

    if stage != "WAITING_MANAGER":
        data["first_approver_id"] = "TEST-MANAGER"
        data["first_approver_role"] = (
            "SALES_MANAGER" if workstream == "SALES"
            else "INSTALLATION_MANAGER"
        )
        data["first_audit_reference"] = "TEST-AUDIT-MANAGER"

    if stage == "APPROVED":
        data["final_approver_id"] = "TEST-COMPTROLLER"
        data["final_approver_role"] = "COMPTROLLER"
        data["final_audit_reference"] = "TEST-AUDIT-FINAL"
        data["audit_evidence"] = "RECORDED"

    return data

source = {
    "view": "fictional_approvals_review_only",
    "manager_authority_verified": False,
    "comptroller_authority_verified": False,
    "live_approval_authorized": False,
    "payment_actions_authorized": False,
    "actual_paid_date_verified": False,
    "rows": [
        row(
            "TEST-SALES-A",
            "Fictional Sales Associate",
            "SALES",
            "WAITING_MANAGER",
        ),
        row(
            "TEST-TECH-B",
            "Fictional Technician",
            "INSTALLATION",
            "WAITING_COMPTROLLER",
        ),
        row(
            "TEST-SALES-C",
            "Fictional Contractor",
            "SALES",
            "APPROVED",
        ),
    ],
    "company_total": "SECRET-DO-NOT-EXPOSE",
}

result = format_fictional_approval_screen_4389(source)
print(json.dumps(result, separators=(",", ":")))
`;

const processResult = spawnSync(
  process.env.VERIDIAN_PYTHON,
  ['-c', pythonSource],
  {
    encoding: 'utf8',
    env: { ...process.env },
    timeout: 30000,
  },
);

assert.equal(
  processResult.status,
  0,
  'Isolated Python adapter failed: ' + processResult.stderr,
);

const pythonOutput = JSON.parse(processResult.stdout);

function render(source, role = 'CEO') {
  return renderToStaticMarkup(
    React.createElement(Component, {
      fictionalSource: source,
      role,
    })
  );
}

test('01 actual Python output renders in approved React review', () => {
  const html = render(pythonOutput);

  assert.match(html, /Fictional Sales Associate/);
  assert.match(html, /Fictional Technician/);
  assert.match(html, /Fictional Contractor/);
  assert.match(html, /Awaiting manager review/);
  assert.match(html, /Awaiting Comptroller approval/);
  assert.match(html, /Two approvals recorded/);
});

test('02 original approval stages and workstreams survive', () => {
  assert.equal(pythonOutput.rows.length, 3);
  assert.deepEqual(
    pythonOutput.rows.map(row => row.stage),
    ['WAITING_MANAGER', 'WAITING_COMPTROLLER', 'APPROVED']
  );

  const sales = render(pythonOutput, 'SALES_MANAGER');
  assert.match(sales, /Fictional Sales Associate/);
  assert.doesNotMatch(sales, /Fictional Technician/);

  const installation = render(
    pythonOutput, 'INSTALLATION_MANAGER'
  );
  assert.match(installation, /Fictional Technician/);
  assert.doesNotMatch(installation, /Fictional Sales Associate/);
});

test('03 unsafe modifications fail before React display', () => {
  const clone = () => structuredClone(pythonOutput);

  const self = clone();
  self.rows[2].final_approver_id = 'TEST-REQUESTER';
  assert.throws(() => render(self));

  const sameApprover = clone();
  sameApprover.rows[2].final_approver_id = 'TEST-MANAGER';
  assert.throws(() => render(sameApprover));

  const elevated = clone();
  elevated.live_approval_authorized = true;
  assert.throws(() => render(elevated));

  const date = clone();
  date.rows[0].actual_paid_date = '2026-11-11';
  assert.throws(() => render(date));
});

test('04 private fields and payment controls remain excluded', () => {
  const html = render(pythonOutput);

  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /bank_account/);
  assert.doesNotMatch(html, /company_total/);
  assert.match(html, /Approval is not payment/);
  assert.doesNotMatch(html, /<button/i);

  assert.equal(pythonOutput.live_approval_authorized, false);
  assert.equal(pythonOutput.payment_actions_authorized, false);
  assert.equal(pythonOutput.actual_paid_date_verified, false);
});
