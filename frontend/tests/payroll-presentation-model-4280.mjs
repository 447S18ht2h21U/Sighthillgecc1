/*
 * Test-only VERIDIAN payroll presentation model.
 * This is NOT a permission service or API integration.
 * Callers may supply ONLY backend-authorized, scoped records.
 * No network, storage, payment issuance or approval actions.
 */

export const money = (cents) => {
  if (!Number.isSafeInteger(cents) || cents < 0) {
    throw new TypeError("Nonnegative integer cents required.");
  }
  return "$" + (cents / 100).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

export const paymentStatus = (record) => {
  if (!record || typeof record !== "object") {
    throw new TypeError("Payment record required.");
  }
  if (record.status === "APPROVED") {
    return "Approved - Not Yet Paid";
  }
  if (record.status === "PAID") {
    if (record.paymentEvidenceVerified !== true) {
      return "Paid - Evidence Not Independently Verified";
    }
    return "Paid - Evidence Verified";
  }
  if (record.status === "DRAFT") {
    return "Draft - Not Approved";
  }
  throw new TypeError("Unknown payment status.");
};

export function ownCompensationView(record) {
  if (!record || !["employee", "contractor"].includes(record.type)) {
    throw new TypeError("Valid employee or contractor record required.");
  }
  if (!["APPROVED", "PAID"].includes(record.status)) {
    throw new TypeError("Unapproved records cannot be disclosed.");
  }

  const amountCents = record.type === "employee"
    ? record.netCents
    : record.finalCents;

  return Object.freeze({
    period: record.period,
    type: record.type,
    compensationKind: record.kind,
    amount: money(amountCents),
    status: paymentStatus(record),
    earnedDate: record.earnedDate ?? null,
    scheduledDate: record.scheduledDate ?? null,
    actualPaidDate: record.actualPaidDate ?? null,
  });
}

export function managerRegisterRows(records) {
  if (!Array.isArray(records)) {
    throw new TypeError("Authorized record collection required.");
  }

  return records.map((record) => {
    if (record.type !== "contractor") {
      throw new TypeError("Contractor register cannot contain employee pay.");
    }
    return Object.freeze({
      contractor: record.displayName,
      project: record.projectCode ?? "Not project-linked",
      period: record.period,
      earnedDate: record.earnedDate ?? null,
      scheduledDate: record.scheduledDate ?? null,
      actualPaidDate: record.actualPaidDate ?? null,
      amount: money(record.finalCents),
      status: paymentStatus(record),
      firstApproval: record.firstApproval ?? "Pending",
      comptrollerApproval: record.comptrollerApproval ?? "Pending",
      exception: Boolean(record.exception),
    });
  });
}

export function companyPayrollSummary(records) {
  if (!Array.isArray(records)) {
    throw new TypeError("Authorized company records required.");
  }

  let contractor = 0;
  let employee = 0;
  let excludedUnpaid = 0;

  for (const record of records) {
    if (!["employee", "contractor"].includes(record.type)) {
      throw new TypeError("Unexpected payroll record type.");
    }

    const amount = record.type === "employee"
      ? record.netCents
      : record.finalCents;

    money(amount);

    if (record.status !== "PAID" ||
        record.paymentEvidenceVerified !== true) {
      excludedUnpaid += amount;
      continue;
    }

    if (record.type === "contractor") contractor += amount;
    else employee += amount;
  }

  return Object.freeze({
    contractorPaid: money(contractor),
    employeePaid: money(employee),
    combinedPaid: money(contractor + employee),
    notCountedAsVerifiedPaid: money(excludedUnpaid),
    basis: "fictional_verified_paid_only",
  });
}