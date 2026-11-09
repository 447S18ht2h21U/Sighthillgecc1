/**
 * Development-only fictional document previews.
 * No project identifier, MSR snapshot, signing, or database mutations.
 */
const previewKinds = [
  { kind: 'EXPEDITED_SERVICE', label: 'Expedited Service Request' },
  { kind: 'COMPLETION_FINANCED', label: 'FINANCED Completion Certificate' },
  { kind: 'COMPLETION_NON_FINANCED', label: 'NON-FINANCED Completion Certificate' },
] as const;

export function FictionalDocumentPreviews4525() {
  if (!import.meta.env.DEV) return null;

  return (
    <details className="veridian-guide-banner veridian-guide-banner--info">
      <summary>Development PDF previews — fictional customer only</summary>
      <p>
        Test-only PDFs. These do not use the selected project or its MSR.
        They do not approve installation, confirm completion, collect
        signatures, or send documents.
      </p>
      <div className="actions">
        {previewKinds.map(item => (
          <a
            key={item.kind}
            className="quiet"
            href={`/api/fictional-document-previews/${item.kind}/`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Preview {item.label}
          </a>
        ))}
      </div>
    </details>
  );
}
