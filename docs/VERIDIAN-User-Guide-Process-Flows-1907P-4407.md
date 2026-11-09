# VERIDIAN User Guide - Process Flowcharts

Document checkpoint: 1907P-4407
System: VERIDIAN Business Operations & Management System
Company: Green Energy Contracting Corporation
Development mode: Isolated previews and protected backend development

## How to read these diagrams

These diagrams explain the intended workflows and the
current development boundaries.

"Approved policy" means a business rule confirmed for VERIDIAN.
"Isolated preview" means fictional presentation data, not live access.
"Backend review required" means production enforcement has not been
established by these presentation tests.

Never use a preview role selector as a real authorization control.
Never interpret recorded payment status as bank-confirmed payment.
Approved historical records must not be silently rewritten.

## 1. Payroll and Compensation workspace

Status: Six-tab fictional React preview accepted.
Real payroll access and payment operations remain disabled.

```mermaid
flowchart TD
    A["Payroll and Compensation workspace"] --> B["My Payroll"]
    A --> C["Weekly Payroll"]
    A --> D["Approvals"]
    A --> E["Payment History"]
    A --> F["Contractor Records"]
    A --> G["Reports"]
    B --> H["Own compensation only"]
    C --> I["Weekly register and approval tracking"]
    D --> J["Manager then Comptroller review"]
    E --> K["Historical obligations and adjustments"]
    F --> L["Onboarding and engagement history"]
    G --> M["Authorized reporting scope"]
    H --> N["Backend identity and scope required for live use"]
    I --> N
    J --> N
    K --> N
    L --> N
    M --> N
```

Role visibility in the preview illustrates approved policy.
Actual personal, manager and company access must be determined
by backend authorization, not by the browser.

## 2. Compensation approval sequence

Status: Approved policy; fictional approval presentation verified.
Operational service integration needs separate review.

```mermaid
flowchart TD
    A["Compensation record prepared"] --> B{"Workstream?"}
    B -->|Sales| C["Sales Manager reviews"]
    B -->|Installation| D["Installation Manager reviews"]
    C --> E{"Manager approves?"}
    D --> E
    E -->|No| F["Remain pending or return for correction"]
    E -->|Yes| G["Comptroller performs final review"]
    G --> H{"Independent approval and audit valid?"}
    H -->|No| F
    H -->|Yes| I["Approved compensation obligation"]
    I --> J["Payment scheduling and issuance process"]
```

No self-approval. Manager and Comptroller responsibilities remain
separate. Durable approval evidence and actual authority must be
verified on the backend.

## 3. Weekly payment evidence and verification

Status: Approved business rules and isolated presentation controls.

```mermaid
flowchart TD
    A["Work period Monday through Sunday"] --> B["Compensation earned"]
    B --> C["Manager and Comptroller approvals"]
    C --> D["Proposed payment date"]
    D --> E["Scheduled following Wednesday"]
    E --> F["Payment issued"]
    F --> G["Payment method and reference retained"]
    G --> H["Settlement candidate evidence"]
    H --> I{"Independent actual-payment evidence verified?"}
    I -->|No| J["Actual paid date remains unverified"]
    I -->|Yes| K["Record verified actual paid date"]
    J --> L["Do not count as verified paid"]
    K --> M["Eligible for verified payment reporting"]
```

A proposed date, scheduled date, issued date or settlement
candidate date is NOT the actual paid date.

The payroll preview currently has no independently verified
actual payment dates. Recorded PAID is not proof of disbursement.

For applicable 1099 reporting, use the legally applicable
payment date, not an invented earned or issuance date.

## 4. Contractor onboarding and eligibility

Status: Approved three-document rule.
Preview shows fictional statuses, not actual document custody.

```mermaid
flowchart TD
    A["Create contractor engagement"] --> B["Collect W-9"]
    B --> C["Review driver's license evidence"]
    C --> D["Review signed contractor agreement"]
    D --> E{"All required documents approved?"}
    E -->|No| F["Pending or rejected: not payment-eligible"]
    E -->|Yes| G["Authorized activation review"]
    G --> H{"Backend authorization and evidence valid?"}
    H -->|No| F
    H -->|Yes| I["Active and payment-eligible engagement"]
    I --> J["Preserve approval and payment history"]
```

The browser cannot activate contractors, verify actual
documents, or authorize disbursement.

## 5. Returning contractor engagement history

Status: Approved policy and tested fictional linkage.

```mermaid
flowchart TD
    A["Original contractor engagement"] --> B["Engagement ends"]
    B --> C["Retain immutable historical association"]
    C --> D["New return engagement reference"]
    D --> E["Link to previous ended engagement"]
    E --> F{"Same contractor and valid later start?"}
    F -->|No| G["Reject invalid return linkage"]
    F -->|Yes| H["Review new engagement onboarding"]
    H --> I["Maintain separate engagement and payment records"]
```

Returning contractors do not overwrite prior engagements.
Historical compensation, approvals and adjustments stay separate.

## 6. Corporate financial reporting lifecycle

Status: Existing Django services and API were identified
at Step 1907P-4406. This is a review diagram, not proof
of full production acceptance.

```mermaid
flowchart TD
    A["Authorized corporate reporting request"] --> B["Choose reporting period"]
    B --> C{"Report type?"}
    C --> D["Income Statement"]
    C --> E["Balance Sheet"]
    C --> F["Cash Flow Statement"]
    C --> G["Project Profitability"]
    D --> H["Create draft snapshot"]
    E --> H
    F --> H
    G --> H
    H --> I["Review calculations, evidence and controls"]
    I --> J{"Approval validation passes?"}
    J -->|No| K["Remain draft or reject approval"]
    J -->|Yes| L["Approved report"]
    L --> M["Immutable historical snapshot"]
    M --> N["Retain audit history"]
```

The inspected reporting API is Comptroller-only.
Do not assume a separate second-person approval is implemented
without examining the full service and authorization rules.

The PostgreSQL approval integrity migration includes protections
against altering approved reports. Preserve these safeguards.

## 7. Financial and payroll data boundaries

Status: Design and security guidance.

```mermaid
flowchart TD
    A["Customer and project records"] --> B["Approved source data and snapshots"]
    B --> C["Project costs and compensation obligations"]
    C --> D["Corporate financial calculations"]
    D --> E["Draft financial report"]
    E --> F["Authorized approval and audit"]
    F --> G["Protected approved report"]
    C --> H["Payroll reporting"]
    H --> I{"Independently verified payment?"}
    I -->|No| J["Recorded or pending, not verified paid"]
    I -->|Yes| K["Verified paid reporting"]
    G --> L["Preserve historic versions"]
    J --> L
    K --> L
```

The Master Sales Record remains the source of truth for
shared customer, project and commercial entries.
Approved MSR versions and signed document snapshots are preserved.

Corporate reporting calculations and payroll reporting must not
silently substitute estimated or unverified figures for actual
financial evidence.

## 8. Development safety and verification workflow

Status: Approved protected batch development practice.

```mermaid
flowchart TD
    A["Confirm protected Git baseline"] --> B["Verify critical source fingerprints"]
    B --> C["Make isolated and approved changes"]
    C --> D["Run focused meaningful tests"]
    D --> E{"Tests and safeguards pass?"}
    E -->|No| F["Stop and investigate without certifying"]
    E -->|Yes| G["Save recovery checkpoint"]
    G --> H["Verify recovery SHA-256 fingerprints"]
    H --> I["Review result before next numbered command"]
    I --> J["Git changes only with explicit approval"]
```

No automatic Git staging, commits or pushes.
Do not target acceptance or operational databases without
specific authorization. Restore tests and recovery verification
must precede production operations.

## Future User Guide work

Add annotated screenshots of each approved interface,
role-based walkthroughs, sample fictional records,
the three-stage Invoice workflow, installation and completion
stage gates, DocuSign evidence checks, and step-by-step
corporate report review once those screens are approved.

This diagram collection is instructional source material.
It does not enable live services or override approved policies.
