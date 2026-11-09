/**
 * VERIDIAN 1907P-4394: isolated fictional Payment History composition.
 * No authorization, real records, live route, payments or exports.
 */
import React from 'react';
import { PayrollPaymentHistory4351 } from './payroll-payment-history-4351';
import { mapFictionalPaymentHistory4393 } from './payroll-history-boundary-4393';

export function PayrollHistoryComposition4394({
  fictionalHistorySource,
}: {
  fictionalHistorySource: unknown;
}): React.JSX.Element {
  const report = mapFictionalPaymentHistory4393(fictionalHistorySource);
  return <PayrollPaymentHistory4351 report={report} />;
}
