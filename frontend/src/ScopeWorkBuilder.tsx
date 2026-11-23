import React from 'react';

type WorkOption = {
  label: string;
  description: string;
};

const WORK_OPTIONS: WorkOption[] = [
  {
    label: 'Replacing Equipment',
    description:
      'Remove and properly dispose of existing equipment. Supply and ' +
      'install replacement equipment, make necessary connections, ' +
      'and test for proper operation.',
  },
  {
    label: 'Service',
    description:
      'Inspect and service existing equipment, perform routine ' +
      'maintenance, check operating conditions, and report findings.',
  },
  {
    label: 'Repair',
    description:
      'Diagnose equipment problems, identify necessary repairs, ' +
      'replace or repair defective components as authorized, ' +
      'and test for proper operation.',
  },
  {
    label: 'New Installation',
    description:
      'Supply and install new equipment, including required materials, ' +
      'connections, startup, and operational testing.',
  },
];

function paragraphs(value: string): string[] {
  return value.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
}

export function inferPrimaryWorkCategory(scope: string): string {
  const parts = paragraphs(scope || '');
  const selected = WORK_OPTIONS.find(option =>
    parts.includes(option.description)
  );

  if (!selected) return '';

  const categories: Record<string, string> = {
    'Replacing Equipment': 'Replacing existing equipment',
    'Service': 'Service',
    'Repair': 'Repair',
    'New Installation': 'New installation',
  };

  return categories[selected.label] ?? '';
}

function compose(selected: string[], custom: string): string {
  const standard = WORK_OPTIONS
    .filter(option => selected.includes(option.label))
    .map(option => option.description);
  return [...standard, custom.trim()].filter(Boolean).join('\n\n');
}

export function ScopeWorkBuilder({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const parts = paragraphs(value || '');
  const selected = WORK_OPTIONS
    .filter(option => parts.includes(option.description))
    .map(option => option.label);

  const custom = parts
    .filter(part => !WORK_OPTIONS.some(option =>
      option.description === part
    ))
    .join('\n\n');

  const changeSelection = (label: string, checked: boolean) => {
    const next = checked
      ? [...selected, label]
      : selected.filter(item => item !== label);
    onChange(compose(next, custom));
  };

  return (
    <section
      aria-label="Scope of Work Builder"
      style={{
        gridColumn: '1 / -1',
        border: '1px solid #D7E3E7',
        borderRadius: 8,
        padding: 16,
      }}
    >
      <h4>Quick Scope of Work</h4>
      <p>Select all that apply.</p>

      <div style={{display:'flex',flexDirection:'column',gap:14,marginBottom:18}}>
        {WORK_OPTIONS.map(option => (
          <label
            key={option.label}
            style={{
              display:'flex',
              alignItems:'center',
              gap:12,
              width:'auto',
              cursor:'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={selected.includes(option.label)}
              onChange={event =>
                changeSelection(option.label, event.target.checked)
              }
              style={{
                width:18,
                height:18,
                minWidth:18,
                margin:0,
                flex:'0 0 18px',
              }}
            />
            <strong style={{fontSize:'1.05rem'}}>{option.label}</strong>
          </label>
        ))}
      </div>

      <details style={{marginBottom:18}}>
        <summary style={{
          display:'inline-block',
          cursor:'pointer',
          background:'#142B3B',
          color:'#FFFFFF',
          padding:'10px 14px',
          borderRadius:4,
          fontWeight:600,
        }}>
          Instructions
        </summary>
        <div style={{padding:'12px 0'}}>
          <p>
            Select one or more work categories. VERIDIAN combines
            their descriptions in the Final Scope of Work below.
          </p>
          {WORK_OPTIONS.map(option => (
            <p key={option.label}>
              <strong>{option.label}:</strong> {option.description}
            </p>
          ))}
          <p>
            Add custom details only when the standard descriptions
            do not cover the proposed work. Review the final wording
            before saving or submitting.
          </p>
        </div>
      </details>

      <label style={{display:'block'}}>
        <strong>Additional or custom work (optional)</strong>
        <textarea
          aria-label="Describe additional or custom work"
          value={custom}
          onChange={event =>
            onChange(compose(selected, event.target.value))
          }
          placeholder="Describe any additional work not covered above..."
          rows={3}
          style={{width:'100%',resize:'vertical',marginTop:8}}
        />
      </label>
    </section>
  );
}
