import { useState } from 'react';
import {
  readFictionalInspection5645,
  readFictionalReview5645,
  saveFictionalReview5645,
  type FictionalInspection5645,
  type FictionalReview5645,
} from './FictionalInspectionScenario5645';

const labels = [
  'Equipment identification',
  'Installation workmanship',
  'Electrical and mechanical connections',
  'System operation',
  'Site condition and documentation',
];

export function FictionalInspectionReview5645() {
  const [inspection, setInspection] = useState<
    FictionalInspection5645 | null
  >(() => readFictionalInspection5645());
  const [review, setReview] = useState<
    FictionalReview5645 | null
  >(() => readFictionalReview5645());
  const [decision, setDecision] = useState<
    '' | 'practice-accepted' | 'practice-corrective-action'
  >('');
  const [note, setNote] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState('');

  function refresh() {
    setInspection(readFictionalInspection5645());
    setReview(readFictionalReview5645());
    setConfirmed(false);
    setError('');
  }

  function record() {
    if (!inspection || !decision || !confirmed || review) return;
    try {
      saveFictionalReview5645(inspection, decision, note);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Practice review failed.');
    }
  }

  return <section style={{
    border:'2px dashed #087F75', borderRadius:'6px',
    padding:'18px', margin:'18px 0'
  }}>
    <h4>Project 104 - Fictional Inspection Review</h4>
    <p><strong>
      SIMULATION ONLY - NOT AN INDEPENDENT OPERATIONAL APPROVAL
    </strong></p>
    <p>Comptroller browser practice. These findings were entered in
      the same browser by the Installation Manager during a fictional
      exercise. Browser storage is not authenticated evidence and can
      be changed locally. No database audit or approval is created.</p>

    <button type="button" className="quiet" onClick={refresh}>
      Refresh fictional inspection findings
    </button>

    {!inspection ? <p role="status">
      No completed fictional inspection is available in this browser.
      Sign in as Installation Manager in the same Chrome browser,
      complete Project 104 - Fictional Installation Practice, then
      return here as Comptroller.
    </p> : <>
      <p>Fictional inspection recorded in browser:
        {' '}{new Date(inspection.completedAt).toLocaleString()}</p>
      <ol>{labels.map((label, index) =>
        <li key={label}>{label}: <strong>{
          inspection.findings[index] === 'pass'
            ? 'Passed - fictional' : 'Failed - fictional'
        }</strong></li>
      )}</ol>
      <p><strong>Practice inspection notes:</strong>
        {' '}{inspection.notes}</p>
      {review ? <p role="status"><strong>{
        review.decision === 'practice-accepted'
          ? 'FICTIONAL PRACTICE REVIEW ACCEPTED'
          : 'FICTIONAL PRACTICE REVIEW - CORRECTIVE ACTION'
      }</strong>. No operational review or approval recorded.
        {' '}{review.note}</p> : <>
        <label style={{display:'block',marginBottom:'12px'}}>
          Fictional review decision
          <select value={decision}
            onChange={e => {
              const v = e.target.value;
              if(v === '' || v === 'practice-accepted' ||
                  v === 'practice-corrective-action') setDecision(v);
            }}>
            <option value="">Choose fictional decision</option>
            <option value="practice-accepted">
              Accept practice findings - fictional
            </option>
            <option value="practice-corrective-action">
              Corrective action - fictional
            </option>
          </select>
        </label>
        <label style={{display:'block',marginBottom:'12px'}}>
          Fictional review note
          <textarea rows={3} maxLength={2000}
            value={note} onChange={e=>setNote(e.target.value)}
            placeholder="Explain this simulated review decision."/>
        </label>
        <label style={{
          display:'flex', alignItems:'flex-start',gap:'10px',
          marginBottom:'12px'
        }}>
          <input type="checkbox" checked={confirmed}
            style={{width:'auto',flex:'0 0 auto',margin:'3px 0 0'}}
            onChange={e=>setConfirmed(e.target.checked)}/>
          <span>I understand this is a fictional browser-only review,
            not verification of physical work or operational evidence.</span>
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="button"
          disabled={!decision || !confirmed ||
            note.trim().length < 15 ||
            (decision === 'practice-accepted' &&
             inspection.findings.includes('fail'))}
          onClick={record}>
          Record fictional practice review
        </button>
      </>}
    </>}
    <p className="muted">
      The separate Independent Installation Inspection Review retains
      its original authorization requirements. This practice cannot
      issue the final Receipt or complete Project 104.
    </p>
  </section>;
}
