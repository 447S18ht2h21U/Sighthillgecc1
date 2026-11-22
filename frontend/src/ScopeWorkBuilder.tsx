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
      <p style={{fontSize: '16px', lineHeight: 1.5}}>
        Select all work that applies. VERIDIAN writes the descriptions.
        Use Describe for custom work.
      </p>
      {WORK_OPTIONS.map(option => (
        <div key={option.label} style={{marginBottom: 14}}>
          <label
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              cursor: 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={selected.includes(option.label)}
              onChange={event =>
                changeSelection(option.label, event.target.checked)
              }
              style={{
                width: 18,
                height: 18,
                minWidth: 18,
                margin: 0,
                marginTop: 2,
                flex: '0 0 18px',
              }}
            />
            <span>
              <strong>{option.label}</strong>
              <small style={{display:'block',marginTop:4}}>
                {option.description}
              </small>
            </span>
          </label>
        </div>
      ))}

      <div style={{marginBottom: 14}}>
        <label style={{display:'block'}}>
          <strong>Describe - Additional or custom work</strong>
          <small style={{display:'block',marginTop:4,marginBottom:8}}>
            Only type details not already covered above.
          </small>
          <textarea
            aria-label="Describe additional or custom work"
            value={custom}
            onChange={event =>
              onChange(compose(selected, event.target.value))
            }
            placeholder="Only type details not covered above..."
            rows={3}
          />
        </label>
      </div>

      <p className="muted">
        Review the generated Scope of work field below.
        You may edit it directly before saving or submitting.
      </p>
    </section>
  );
}
