import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  money,
  paymentStatus,
  ownCompensationView,
  managerRegisterRows,
  companyPayrollSummary,
} from "./payroll-presentation-model-4280.mjs";

const employee = Object.freeze({
  type: "employee",
  period: "2026-11-02 to 2026-11-08",
  kind: "SALARY",
  netCents: 400000,
  status: "PAID",
  paymentEvidenceVerified: true,
  actualPaidDate: "2026-11-11",
});

const contractor = Object.freeze({
  type: "contractor",
  displayName: "Fictional Contractor A",
  projectCode: "DEMO-001",
  period: "2026-11-02 to 2026-11-08",
  kind: "COMMISSION",
  finalCents: 850000,
  earnedDate: "2026-11-03",
  scheduledDate: "2026-11-11",
  actualPaidDate: "2026-11-11",
  status: "PAID",
  paymentEvidenceVerified: true,
  firstApproval: "Approved",
  comptrollerApproval: "Approved",
});

const approvedUnpaid = Object.freeze({
  ...contractor,
  displayName: "Fictional Contractor B",
  projectCode: "DEMO-002",
  finalCents: 50000,
  actualPaidDate: null,
  status: "APPROVED",
  paymentEvidenceVerified: false,
  comptrollerApproval: "Approved",
});

test("currency values use cents and two decimals", () => {
  assert.equal(money(125000), "$1,250.00");
  assert.equal(money(0), "$0.00");
  assert.throws(() => money(-1));
  assert.throws(() => money(10.5));
  assert.throws(() => money(Infinity));
});

test("approved and paid are clearly different", () => {
  assert.equal(paymentStatus(approvedUnpaid), "Approved - Not Yet Paid");
  assert.equal(paymentStatus(contractor), "Paid - Evidence Verified");
  assert.match(
    paymentStatus({ ...contractor, paymentEvidenceVerified: false }),
    /Not Independently Verified/
  );
  assert.equal(
    paymentStatus({ status: "DRAFT" }),
    "Draft - Not Approved"
  );
});

test("my compensation displays no private identifiers or peer data", () => {
  const row = ownCompensationView(approvedUnpaid);
  assert.equal(row.amount, "$500.00");
  assert.equal(row.status, "Approved - Not Yet Paid");
  assert.equal(row.actualPaidDate, null);
  assert.ok(!("displayName" in row));
  assert.ok(!("projectCode" in row));
  assert.ok(!("bankAccount" in row));
  assert.throws(() => ownCompensationView({
    ...approvedUnpaid, status: "DRAFT",
  }));
  assert.equal(ownCompensationView(employee).amount, "$4,000.00");
});

test("manager presentation distinguishes approvals and actual payment", () => {
  const rows = managerRegisterRows([contractor, approvedUnpaid]);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].project, "DEMO-001");
  assert.equal(rows[1].status, "Approved - Not Yet Paid");
  assert.equal(rows[1].actualPaidDate, null);
  assert.equal(rows[1].comptrollerApproval, "Approved");
  assert.ok(!("bankAccount" in rows[0]));
  assert.throws(() => managerRegisterRows([employee]));
});

test("company paid totals exclude approved unpaid obligations", () => {
  const result = companyPayrollSummary([
    employee, contractor, approvedUnpaid,
  ]);
  assert.deepEqual(result, {
    contractorPaid: "$8,500.00",
    employeePaid: "$4,000.00",
    combinedPaid: "$12,500.00",
    notCountedAsVerifiedPaid: "$500.00",
    basis: "fictional_verified_paid_only",
  });
});

test("missing independent payment evidence is not counted as verified paid", () => {
  const result = companyPayrollSummary([
    { ...contractor, paymentEvidenceVerified: false },
  ]);
  assert.equal(result.combinedPaid, "$0.00");
  assert.equal(result.notCountedAsVerifiedPaid, "$8,500.00");
});

test("presentation remains isolated from live application and APIs", () => {
  const model = fs.readFileSync(
    new URL("./payroll-presentation-model-4280.mjs", import.meta.url),
    "utf8"
  );
  assert.doesNotMatch(model, /\bfetch\s*\(|\bXMLHttpRequest\b|\bWebSocket\b/);
  assert.doesNotMatch(model, /from\s+["']\.\.\/src\//);
  assert.match(model, /NOT a permission service/);
});