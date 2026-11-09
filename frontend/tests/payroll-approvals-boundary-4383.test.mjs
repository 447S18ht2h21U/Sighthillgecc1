import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { transformSync } from 'esbuild';

const source = readFileSync(
  resolve('tests/payroll-approvals-boundary-4383.ts'), 'utf8'
);
const code = transformSync(source, {
  loader: 'ts', format: 'esm', target: 'es2022'
}).code;
const mod = await import(
  'data:text/javascript;base64,' +
  Buffer.from(code).toString('base64')
);
const map = mod.mapFictionalApprovals4383;

function fixture() {
  return {
    view: 'fictional_approvals_review_only',
    manager_authority_verified: false,
    comptroller_authority_verified: false,
    live_approval_authorized: false,
    payment_actions_authorized: false,
    actual_paid_date_verified: false,
    rows: [{
      reference: 'TEST-001',
      recipient: 'Fictional Contractor',
      workstream: 'SALES',
      amount: '1250.00',
      requester_id: 'TEST-REQUESTER',
      first_approver_id: null,
      final_approver_id: null,
      stage: 'WAITING_MANAGER',
      audit_evidence: 'PENDING',
      actual_paid_date: null,
      actual_paid_date_verified: false,
      bank_account: 'SECRET-DO-NOT-EXPOSE'
    }]
  };
}

test('01 synthetic source maps to approved React contract', () => {
  const result = map(fixture());
  assert.equal(result.rows[0].amount, '1250.00');
  assert.equal(result.rows[0].requesterId, 'TEST-REQUESTER');
  assert.equal(result.liveApprovalAuthorized, false);
});

test('02 all three approval stages preserve separation', () => {
  const waiting = fixture();
  assert.equal(map(waiting).rows[0].stage, 'WAITING_MANAGER');

  waiting.rows[0].first_approver_id = 'TEST-MANAGER';
  waiting.rows[0].stage = 'WAITING_COMPTROLLER';
  assert.equal(map(waiting).rows[0].stage, 'WAITING_COMPTROLLER');

  waiting.rows[0].final_approver_id = 'TEST-COMPTROLLER';
  waiting.rows[0].stage = 'APPROVED';
  waiting.rows[0].audit_evidence = 'RECORDED';
  assert.equal(map(waiting).rows[0].stage, 'APPROVED');
});

test('03 self-approval and duplicate approvers are rejected', () => {
  const self = fixture();
  self.rows[0].first_approver_id = 'TEST-REQUESTER';
  assert.throws(() => map(self));

  const duplicate = fixture();
  duplicate.rows[0].first_approver_id = 'TEST-MANAGER';
  duplicate.rows[0].final_approver_id = 'TEST-MANAGER';
  duplicate.rows[0].stage = 'APPROVED';
  duplicate.rows[0].audit_evidence = 'RECORDED';
  assert.throws(() => map(duplicate));
});

test('04 final approval requires complete recorded evidence', () => {
  const data = fixture();
  data.rows[0].stage = 'APPROVED';
  data.rows[0].first_approver_id = 'TEST-MANAGER';
  data.rows[0].final_approver_id = 'TEST-COMPTROLLER';
  assert.throws(() => map(data));
});

test('05 elevated authority, real IDs and paid dates fail closed', () => {
  const elevated = fixture();
  elevated.live_approval_authorized = true;
  assert.throws(() => map(elevated));

  const realId = fixture();
  realId.rows[0].requester_id = '12345';
  assert.throws(() => map(realId));

  const paidDate = fixture();
  paidDate.rows[0].actual_paid_date = '2026-11-11';
  assert.throws(() => map(paidDate));
});

test('06 private source keys are removed and no live access exists', () => {
  const data = fixture();
  data.tax_identifier = 'SECRET-DO-NOT-EXPOSE';
  const result = map(data);
  assert.doesNotMatch(JSON.stringify(result), /SECRET-DO-NOT-EXPOSE/);
  assert.equal(result.managerAuthorityVerified, false);
  assert.equal(result.comptrollerAuthorityVerified, false);
  assert.equal(mod.approvalsBoundaryGrantsLiveAccess4383(), false);
});
