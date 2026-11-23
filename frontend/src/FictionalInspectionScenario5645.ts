/*
 * Project 104 fictional scenario storage.
 * Browser-local, user-editable, untrusted. NEVER operational evidence.
 * Not a signature, inspection, approval, audit event, or payment.
 */
export const FICTIONAL_PROJECT_104 =
  '5e02a9d2-1028-41ea-a3bd-624116ef3b0b';

const inspectionKey = 'veridian-fictional-104-inspection-v1';
const reviewKey = 'veridian-fictional-104-inspection-review-v1';

export type FictionalInspection5645 = {
  version: 1;
  classification: 'BROWSER_ONLY_FICTIONAL';
  projectId: string;
  completedAt: string;
  findings: ('pass' | 'fail')[];
  notes: string;
};

export type FictionalReview5645 = {
  version: 1;
  classification: 'BROWSER_ONLY_FICTIONAL';
  projectId: string;
  sourceCompletedAt: string;
  reviewedAt: string;
  decision: 'practice-accepted' | 'practice-corrective-action';
  note: string;
};

export function readFictionalInspection5645():
    FictionalInspection5645 | null {
  try {
    const raw = localStorage.getItem(inspectionKey);
    if (!raw) return null;
    const x: unknown = JSON.parse(raw);
    if (typeof x !== 'object' || !x) return null;
    const value = x as Partial<FictionalInspection5645>;
    if (
      value.version !== 1 ||
      value.classification !== 'BROWSER_ONLY_FICTIONAL' ||
      value.projectId !== FICTIONAL_PROJECT_104 ||
      typeof value.completedAt !== 'string' ||
      !Number.isFinite(Date.parse(value.completedAt)) ||
      !Array.isArray(value.findings) ||
      value.findings.length !== 5 ||
      !value.findings.every(f => f === 'pass' || f === 'fail') ||
      typeof value.notes !== 'string' ||
      value.notes.trim().length < 15 ||
      value.notes.length > 2000
    ) return null;
    return value as FictionalInspection5645;
  } catch {
    return null;
  }
}

export function saveFictionalInspection5645(
  findings: ('pass'|'fail')[], notes: string
) {
  if (
    findings.length !== 5 ||
    findings.some(f => f !== 'pass' && f !== 'fail') ||
    notes.trim().length < 15 ||
    notes.length > 2000
  ) throw new Error('Complete the five fictional findings and notes.');
  const value: FictionalInspection5645 = {
    version: 1,
    classification: 'BROWSER_ONLY_FICTIONAL',
    projectId: FICTIONAL_PROJECT_104,
    completedAt: new Date().toISOString(),
    findings: [...findings],
    notes: notes.trim()
  };
  localStorage.removeItem(reviewKey);
  localStorage.setItem(inspectionKey, JSON.stringify(value));
}

export function clearFictionalInspection5645() {
  localStorage.removeItem(inspectionKey);
  localStorage.removeItem(reviewKey);
}

export function readFictionalReview5645():
    FictionalReview5645 | null {
  try {
    const raw = localStorage.getItem(reviewKey);
    if (!raw) return null;
    const x: unknown = JSON.parse(raw);
    if (typeof x !== 'object' || !x) return null;
    const value = x as Partial<FictionalReview5645>;
    const inspection = readFictionalInspection5645();
    if (
      !inspection ||
      value.version !== 1 ||
      value.classification !== 'BROWSER_ONLY_FICTIONAL' ||
      value.projectId !== FICTIONAL_PROJECT_104 ||
      value.sourceCompletedAt !== inspection.completedAt ||
      typeof value.reviewedAt !== 'string' ||
      !Number.isFinite(Date.parse(value.reviewedAt)) ||
      (value.decision !== 'practice-accepted' &&
       value.decision !== 'practice-corrective-action') ||
      typeof value.note !== 'string' ||
      value.note.trim().length < 15 ||
      value.note.length > 2000
    ) return null;
    return value as FictionalReview5645;
  } catch {
    return null;
  }
}

export function saveFictionalReview5645(
  inspection: FictionalInspection5645,
  decision: FictionalReview5645['decision'],
  note: string
) {
  const current = readFictionalInspection5645();
  if (!current || current.completedAt !== inspection.completedAt) {
    throw new Error('Fictional inspection changed. Refresh before review.');
  }
  if (readFictionalReview5645()) {
    throw new Error('Practice review already recorded in this browser.');
  }
  if (note.trim().length < 15 || note.length > 2000) {
    throw new Error('A fictional review note of 15-2000 characters is required.');
  }
  if (decision === 'practice-accepted' &&
      inspection.findings.some(f => f === 'fail')) {
    throw new Error('Failed practice findings require corrective action.');
  }
  const value: FictionalReview5645 = {
    version: 1,
    classification: 'BROWSER_ONLY_FICTIONAL',
    projectId: FICTIONAL_PROJECT_104,
    sourceCompletedAt: inspection.completedAt,
    reviewedAt: new Date().toISOString(),
    decision,
    note: note.trim()
  };
  localStorage.setItem(reviewKey, JSON.stringify(value));
}
