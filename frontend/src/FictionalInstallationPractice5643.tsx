import { useState } from 'react';
import { saveFictionalInspection5645, clearFictionalInspection5645 } from './FictionalInspectionScenario5645';

type Finding = '' | 'pass' | 'fail';

const items = [
  'Practice check 1 ? Equipment identification',
  'Practice check 2 ? Installation workmanship',
  'Practice check 3 ? Electrical and mechanical connections',
  'Practice check 4 ? System operation',
  'Practice check 5 ? Site condition and documentation',
] as const;

export function FictionalInstallationPractice5643() {
  const [installation, setInstallation] = useState(false);
  const [findings, setFindings] = useState<Finding[]>(
    () => items.map(() => '')
  );
  const [notes, setNotes] = useState('');
  const [recorded, setRecorded] = useState(false);

  const complete = findings.every(value => value !== '');
  const failed = findings.some(value => value === 'fail');
  const ready = installation && complete &&
    notes.trim().length >= 15 && !recorded;

  const reset = () => {
    setInstallation(false);
    setFindings(items.map(() => ''));
    setNotes('');
    setRecorded(false);
    clearFictionalInspection5645();
  };

  return (
    <section
      className="installation-completion-guidance"
      aria-label="Project 104 fictional installation practice"
      style={{
        border: '2px dashed #087F75',
        padding: '18px',
        marginTop: '18px'
      }}
    >
      <h3>Project 104 ? Fictional Installation Practice</h3>
      <p><strong>
        SIMULATION ONLY ? NO ACTUAL INSTALLATION OR INSPECTION
      </strong></p>
      <p>
        Practice the installation and inspection steps for Project 104.
        Answers stay in this browser session only. This exercise cannot
        update Installation Scheduling, Record Installation Inspection,
        Project Completion Review, payment records, or DocuSign evidence.
      </p>

      <label style={{
        display: 'flex', alignItems: 'flex-start',
        gap: '10px', margin: '16px 0'
      }}>
        <input
          type="checkbox"
          style={{width: 'auto', flex: '0 0 auto', margin: '3px 0 0'}}
          checked={installation}
          disabled={recorded}
          onChange={event => setInstallation(event.target.checked)}
        />
        <span>
          For this fictional exercise, assume the installation has
          been completed. I am not certifying actual work.
        </span>
      </label>

      <h4>Practice inspection findings</h4>
      {items.map((item, index) => (
        <label key={item} style={{
          display: 'block', marginBottom: '14px'
        }}>
          <span style={{display: 'block', marginBottom: '5px'}}>
            {item}
          </span>
          <select
            value={findings[index]}
            disabled={!installation || recorded}
            onChange={event => {
              const choice = event.target.value;
              if (choice !== '' && choice !== 'pass' &&
                  choice !== 'fail') return;
              setFindings(previous => previous.map(
                (value, position) =>
                  position === index ? choice : value
              ));
            }}
          >
            <option value="">Choose fictional result</option>
            <option value="pass">Passed ? fictional</option>
            <option value="fail">Failed ? fictional</option>
          </select>
        </label>
      ))}

      <label style={{display: 'block', marginBottom: '12px'}}>
        Practice inspection notes
        <textarea
          rows={3}
          value={notes}
          maxLength={2000}
          disabled={!installation || recorded}
          placeholder="Describe hypothetical findings. No physical inspection is asserted."
          onChange={event => setNotes(event.target.value)}
        />
      </label>

      {!recorded ? (
        <button type="button"
          disabled={!ready}
          onClick={() => {
            try {
              saveFictionalInspection5645(
                findings as ('pass'|'fail')[], notes
              );
              setRecorded(true);
            } catch (error) {
              window.alert(error instanceof Error
                ? error.message : 'Unable to save practice.');
            }
          }}
        >
          Complete fictional inspection practice
        </button>
      ) : (
        <p role="status">
          <strong>
            {failed
              ? 'FICTIONAL INSPECTION: CORRECTIVE ACTION REQUIRED'
              : 'FICTIONAL INSPECTION: ALL PRACTICE CHECKS PASSED'}
          </strong>
          {' ? '}Practice complete in browser memory only.
          No inspection evidence or operational approval was recorded.
        </p>
      )}

      <button type="button" className="quiet"
        style={{marginLeft: '8px'}}
        onClick={reset}>
        Reset fictional practice
      </button>

      <p className="muted">
        The actual Record Installation Inspection workflow remains
        restricted to the assigned Installation Manager after verified
        operational installation completion. Independent Comptroller
        review and DocuSign evidence are separate requirements.
      </p>
    </section>
  );
}
