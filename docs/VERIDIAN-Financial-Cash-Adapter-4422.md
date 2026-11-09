# VERIDIAN Read-Only Cash Evidence Adapter

Checkpoint: 1907P-4422
Status: ISOLATED ORM ADAPTER - NOT AN OPERATIONAL CASH FLOW REPORT

## What this component reads

Customer bank confirmations are matched to verified customer
payments. If an approved adjustment exists, the payment is
withheld pending separate adjustment and bank review.

Contractor settlement verifications are matched against payment
issuance, paid status, cleared amount, and independent verifier.

The settlement date determines the reporting period for the
contractor disbursement. The customer bank-confirmation date
determines the reporting period for the customer receipt.

## Reporting boundaries

The result is explicitly a PARTIAL cash movement total.

It does not represent complete corporate cash flow or a bank
balance. It does not yet include employee settlements, verified
refund outflows, external bank charges, financing or other
corporate receipts and expenditures.

The first isolated database test verifies read-only queries
against an empty disposable SQLite database. Individual
populated evidence cases are verified with fictional in-memory
objects. Populated ORM integration remains a future test.

## Process flow

```mermaid id="tkpbd8"
flowchart TD
    A["Read existing bank confirmations and contractor settlements"] --> B["Match to corresponding original records"]
    B --> C{"Valid amount, dates, status and independent evidence?"}
    C -->|No| D["Withhold from partial total and explain"]
    C -->|Yes| E["Check accounting period"]
    E --> F["Classify receipt or settled disbursement"]
    F --> G["Calculate partial movement total"]
    D --> H["Retain outstanding evidence requirements"]
    G --> I["Require full bank reconciliation and missing flows"]
    H --> I
    I --> J["No financial statement certification or operational approval"]
```

No existing corporate financial service, API, historical report,
payment record or operational database is modified by this step.
The approved CEO financial-report approval feature remains off.
