# VERIDIAN User Guide

**Application:** VERIDIAN Business Operations & Management System
**Organization:** Sighthill Associates, Inc.
**Status:** Living development draft
**Version:** 0.1
**Started:** October 20, 2026

## 1. Introduction

VERIDIAN manages customers, projects, Master Sales Records, documents, installations, payments, personnel, and reporting.
Access to records and actions depends on approved roles, project assignments, and authorizations.

## 2. Foundational Record Relationships

Customer -> Project -> Master Sales Record -> Contract / Invoice / Completion Certificate

One customer may have multiple projects. Each project maintains its own commercial records and approved MSR history.

### Master Sales Record controls

Draft records may be edited. Submitted records require authorized review. Approved versions are immutable; commercial changes require a new version.

### Financing

- Financed: 50% deposit and 50% balance.
- Non-financed: 100% due upon completion.

## 3. Planned Chapters

1. Navigation and roles
2. Customers and contacts
3. Projects and MSR approval
4. Contracts, invoices, and signatures
5. Installation scheduling and completion
6. Customer payments
7. Project Status Dashboard
8. Employees and contractors
9. Compensation and payroll
10. Financial reporting
11. Temporary duties and project access
12. Administration and audit history
13. Troubleshooting and production operations

## 4. Verification Register

| Area | Status |
| --- | --- |
| Customer-project-MSR relationships | Initial draft |
| Signing workflows | Production verification pending |
| Financial reports | Accountant validation pending |
| Screen instructions | To be developed |

This guide will be expanded as each application workflow is verified.

## 5. Customer-to-Project Operating Workflow

**Verification:** Navigation and controls inspected in frontend source on October 20, 2026. Browser walkthrough pending.

### 5.1 Create a customer

1. Open **Customers & projects**.
2. Select **Add customer**.
3. Enter the required legal name and billing address.
4. Enter email and telephone information when available.
5. Provide a duplicate override reason if legitimately required.
6. Select **Save customer**.

### 5.2 Create a project

1. Open **Customers & projects**.
2. Select **Create project**.
3. Choose an existing, active customer.
4. Enter the installation address.
5. Assign a Sales Associate and Sales Manager.
6. Supply a duplicate override reason when applicable.
7. Select **Create draft**.

### 5.3 Prepare the Master Sales Record

1. Open the project from the Customers & Projects workspace.
2. Locate the current draft Master Sales Record.
3. Complete the scope, equipment, materials, commercial information, and pricing.
4. Select the appropriate financing classification. The payment option updates automatically.
5. Select **Save draft** to retain an editable draft or **Save & submit** to request review.

### 5.4 Review and approve

1. An authorized reviewer opens the submitted project record.
2. Review the submitted commercial information.
3. Select **Approve version** to approve or **Reject with reason** to reject.
4. Approved MSR versions are locked against direct commercial edits.

### 5.5 Revise approved commercial information

1. Open the project containing the current approved MSR.
2. Enter a review note or revision reason.
3. Select **Create revision**.
4. Edit and submit the new draft through the normal approval workflow.
5. Preserve earlier approved versions as historical records.

### 5.6 Authorization notes

The current customer and project creation controls are visible to Sales Associates, Sales Managers, and the Comptroller. Other access and approval actions depend on role and authorized project scope.

**Verification pending:** Complete a role-by-role browser walkthrough before treating these instructions as final training material.

## 6. Documents and Installation Eligibility

**Verification:** Document controls and installation eligibility service inspected on October 20, 2026. End-to-end browser verification remains pending.

### 6.1 Prepare project documents

1. Open a project with a current approved Master Sales Record.
2. In the Documents section, an authorized user may select **Prepare contract**, **Prepare invoice**, or **Prepare completion certificate**.
3. Download the prepared interactive PDF.
4. Treat prepared PDFs as unsigned copies; document preparation does not establish a completed signature.
5. The completion certificate variant depends on the approved financing classification.

### 6.2 Customer signatures

The customer must sign the contract and invoice before the authorized GECC signer under the approved commercial signing sequence.
Installation eligibility requires verified customer signature evidence for both documents associated with the current approved MSR.
Production signing remains disabled pending release. Sandbox testing must not be treated as production execution.

### 6.3 Installation eligibility rules

The installation eligibility service requires all of the following:
- A current approved MSR.
- Verified customer contract signature evidence.
- Verified customer invoice signature evidence.
- Verified cancellation deadline evidence.
- Expiration of five calendar days after the later customer contract or invoice signature.
- Expiration of the applicable verified cancellation deadline.
- A valid financing classification.
- For financed customers, a verified 50% deposit after approved payment adjustments.

The effective eligibility time is the later of the five-day waiting-period expiry and the cancellation deadline, evaluated using Eastern Time.

### 6.4 Financing-specific payment requirements

**Financed:** The verified payments for the current approved MSR, less approved adjustments, must equal or exceed 50% of its approved total price before installation eligibility is granted.

**Non-financed:** This eligibility function does not require an advance deposit. The approved payment arrangement is 100% upon completion.

### 6.5 Completion certificates

VERIDIAN provides distinct preparation copies for financed and non-financed completion certificates. Completion and signature dates remain blank during preparation.
Operational work completion is not equivalent to receipt of a properly signed completion certificate.

### 6.6 Remaining verification

Verify the actual scheduling and completion API call paths, user-facing eligibility messages, signature evidence lifecycle, and applicable role permissions before finalizing this chapter for production training.

### 6.7 Understanding Installation Readiness

Installation readiness identifies which verified requirements have been satisfied and which conditions still prevent installation eligibility. A project is eligible only when every required condition is satisfied.

Common blocking conditions include:
- No current approved Master Sales Record.
- Missing verified contract or invoice signature evidence.
- Missing, invalid, or unexpired cancellation deadline evidence.
- The five-calendar-day waiting period has not expired.
- A financed customer has not satisfied the 50% net verified deposit requirement.
- The approved MSR contains an invalid or missing financing classification.

Approved payment adjustments reduce the amount counted toward the financed deposit requirement. Non-financed customers do not require an advance deposit under this eligibility rule.

Installation readiness does not itself authorize an employee to schedule installation. Scheduling remains subject to the separate role, project-access, and operational authorization controls.

If a project is blocked, review the reported reasons and resolve the underlying requirement through the authorized workflow. Do not alter approved historical records or immutable verification evidence to bypass a blocking condition.

## Appendix A. Git Repository and Version References

VERIDIAN source code is maintained using Git. The following references identify the development repository and a verified local checkpoint.

- **GitHub repository:** https://github.com/447S18ht2h21U/Sighthillgecc1
- **Local development directory:** C:\Users\whody\GECC-local
- **Development branch:** `gecc/contractor-compensation-2026-10-08`
- **Verified local commit:** `383a821`
- **Commit description:** Verify installation readiness safeguards and update VERIDIAN user guidance
- **User Guide source file:** `docs/VERIDIAN-User-Guide-v1.md`

**Publication status:** Commit `383a821` has been verified locally. Its publication to GitHub has not been authorized or confirmed. Do not assume that the remote repository contains this checkpoint.

**Version control practice:** Record significant development milestones using approved local Git commits. A GitHub push requires separate authorization. Diagnostic regression logs are excluded from this checkpoint.
