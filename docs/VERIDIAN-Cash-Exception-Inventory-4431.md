# Consolidated Cash-Evidence Exception Inventory

Checkpoint: 1907P-4431
Status: Isolated read-only preview; not operational.

This component brings together the existing refund and
employee payroll evidence exceptions and adds approved
payroll records that have not yet been issued.

## Evidence workflow

```mermaid
flowchart TD
    A["Review accounting records"] --> B{"Evidence category"}
    B --> C["Refund approved; bank clearing not proven"]
    B --> D["Payroll approved; issuance missing"]
    B --> E["Payroll issued; Paid status missing"]
    B --> F["Payroll Paid; bank settlement missing"]
    C --> G["Record exception and required evidence"]
    D --> G
    E --> G
    F --> G
    G --> H["Independent bank reconciliation required"]
    H --> I["No cash certification or financial approval"]
```

All dates are review dates, not certified bank movement dates.
An approved payroll period end is never a cash settlement date.

The exception inventory is incomplete and must not be used as
a full financial report. The existing financial services,
payment states, historical records and role permissions remain
unchanged. CEO financial approval stays disabled by default.
