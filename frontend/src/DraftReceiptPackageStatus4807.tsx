import React, { useEffect, useState } from 'react';

type DraftPackageReport = {
  project_id: string;
  read_only: true;
  status: 'NO_DRAFT_PACKAGE' | 'PREREQUISITES_MISSING'
    | 'SCHEMA_UNAVAILABLE' | 'INTEGRITY_FAILED'
    | 'VERIFIED_DRAFT_RETAINED';
  storage_available: boolean;
  draft_package_count: number;
  verified_draft_package_count: number;
  integrity_verified: boolean;
  draft_only: true;
  final_receipt_verified: false;
  issuance_authorized: false;
  provider_email_authenticated: false;
  customer_delivery_verified: false;
  completion_authorized: false;
};

export function DraftReceiptPackageStatus4807({
  projectId,
}: {
  projectId: string;
}) {
  const [report, setReport] = useState<DraftPackageReport | null>(null);
  const [message, setMessage] = useState('Checking draft Receipt package...');
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setReport(null);
    setVisible(true);
    setMessage('Checking draft Receipt package...');

    void (async () => {
      try {
        const response = await fetch(
          `/api/operational-projects/${encodeURIComponent(projectId)}/draft-receipt-package/`,
          {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'no-store',
            signal: controller.signal,
          },
        );

        if (response.status === 401 || response.status === 403
          || response.status === 404) {
          if (!controller.signal.aborted) setVisible(false);
          return;
        }

        if (!response.ok) {
          throw new Error('Draft package status cannot be retrieved.');
        }

        const data: DraftPackageReport = await response.json();

        if (
          data.project_id !== projectId
          || data.read_only !== true
          || data.draft_only !== true
          || data.final_receipt_verified !== false
          || data.issuance_authorized !== false
          || data.provider_email_authenticated !== false
          || data.customer_delivery_verified !== false
          || data.completion_authorized !== false
          || ![
            'NO_DRAFT_PACKAGE',
            'PREREQUISITES_MISSING',
            'SCHEMA_UNAVAILABLE',
            'INTEGRITY_FAILED',
            'VERIFIED_DRAFT_RETAINED',
          ].includes(data.status)
          || (data.status === 'VERIFIED_DRAFT_RETAINED' && (
            data.integrity_verified !== true
            || data.storage_available !== true
            || data.verified_draft_package_count < 1
            || data.verified_draft_package_count !== data.draft_package_count
          ))
        ) {
          throw new Error('Draft package response failed verification.');
        }

        if (!controller.signal.aborted) {
          setReport(data);
          setMessage('');
        }
      } catch {
        if (!controller.signal.aborted) {
          setReport(null);
          setMessage('Draft package status unavailable or unverified.');
        }
      }
    })();

    return () => controller.abort();
  }, [projectId]);

  if (!visible) return null;

  return (
    <section aria-label="Draft Receipt package status">
      <strong>Draft Receipt Package</strong>
      {message && <p role="status">{message}</p>}
      {report && (
        <p role="status">
          {report.status === 'VERIFIED_DRAFT_RETAINED'
            ? `Verified draft retained (${report.verified_draft_package_count} package(s)).`
            : report.status === 'SCHEMA_UNAVAILABLE'
              ? 'Draft package storage unavailable; migration not applied.'
              : report.status === 'INTEGRITY_FAILED'
                ? 'Draft package verification failed. Review required.'
                : report.status === 'PREREQUISITES_MISSING'
                  ? 'Current approved project record required.'
                  : 'No verified draft package retained.'}
        </p>
      )}
      <p className="muted">
        Draft evidence only. Final Receipt issuance, provider-authenticated
        customer delivery, and project completion are not verified.
      </p>
    </section>
  );
}
