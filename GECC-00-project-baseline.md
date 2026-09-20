\# GECC-00-project-baseline.md



\# GECC Sales Back Office System — Project Baseline



\## Bundle Metadata



\- Bundle name: GECC-00-project-baseline.md

\- Project: GECC Sales Back Office System

\- Company: Go Ecco Climate Control

\- Company abbreviation: GECC

\- Bundle type: Authoritative project baseline

\- Status: Approved baseline for development planning

\- Created date: 2026-09-19

\- Previous bundle: None

\- Next planned bundle: GECC-01-data-model.md

\- Primary database: Robust searchable relational database

\- Google Sheets: Optional export or reporting destination; not the system of record



\---



\## 1. Project Purpose



GECC needs a unified sales back-office system that eliminates repetitive data entry and manual document preparation.



The system must allow a Sales Associate to enter project information once into a Master Sales Record. That information must then be reused consistently to generate:



\- Invoice

\- Contract

\- Certificate

\- Contractor commission reports

\- Payroll or contractor-payment summaries

\- Accounts receivable records

\- Accounts payable records

\- Project profitability reports

\- Customer profitability reports

\- Balance sheet

\- Cash-flow statement

\- Statement of operations

\- Inventory records

\- Fixed-asset records

\- Other approved system outputs



The system must prevent inconsistent data and preserve a complete audit trail of all records, documents, approvals, signatures, payments, revisions, and access activity.



\---



\## 2. Business Description



GECC is an HVAC sales and HVAC service company.



GECC canvasses neighborhoods to find residential customers who need to:



\- Replace HVAC equipment

\- Repair HVAC equipment

\- Service HVAC equipment

\- Remove old equipment

\- Install new equipment



Different people perform different functions, including:



\- Sales

\- Installation

\- Technical work

\- Database administration

\- Accounts payable

\- Payroll or contractor-payment administration

\- Financial management



GECC has approximately twelve employees or contractors:



\- 4 Sales Associates

\- 3 Technicians

\- 1 Sales Manager

\- 1 Installation Manager

\- 1 Database Administrator

\- 1 Accounts Payable Associate

\- 1 Comptroller



All workers are classified as independent contractors and are responsible for their own taxes and benefits.



\---



\## 3. Core Business Problem



The current process requires the same information to be entered repeatedly into:



1\. A Google spreadsheet serving as an informal database

2\. An invoice

3\. A contract

4\. A certificate

5\. Contractor payroll or commission records

6\. Financial reporting records



Documents are manually downloaded as PDFs and manually transferred for signature.



The new system must replace repetitive entry, manual document preparation, manual document transfer, inconsistent records, and fragmented reporting.



\---



\## 4. Project Success Criteria



The system is successful when:



\- A Sales Associate enters sale information once.

\- A Master Sales Record is created for every project.

\- The Master Sales Record is the single source of truth for that project.

\- Generated documents use the approved Master Sales Record.

\- No repetitive document data entry is required.

\- Contracts and certificates are populated automatically from existing PDF templates.

\- Invoices are generated automatically.

\- Documents can be saved, printed, emailed, and sent for electronic signature.

\- Contractor commission reports are generated automatically.

\- Financial reports are generated automatically.

\- Records are searchable.

\- Access is authorization-based.

\- Original records and all revisions are retained permanently.

\- Financial amounts and documents remain consistent.

\- Every significant action is auditable.

\- Approved records cannot be changed by unauthorized users.

\- Project status and outstanding tasks are visible through an activity dashboard.



\---



\## 5. Explicitly Out of Scope



The system must not:



\- Schedule neighborhood canvassing

\- Schedule technicians beyond project installation tasks

\- Track technician time

\- Track technician GPS locations

\- Manage employee benefits

\- Manage hiring

\- Manage general HR records

\- Replace general HR software

\- Automatically import bank statements during the initial implementation

\- Treat Google Sheets as the primary database



Google Sheets may be used as an export or reporting destination.



\---



\## 6. Primary System Principles



\### 6.1 Single source of truth



Each project has one Master Sales Record. Customer, project, pricing, scope, equipment, cost, payment, document, commission, and profitability information must be linked to that record.



\### 6.2 Controlled state machine



Users must not be able to skip required steps or perform actions out of order.



\### 6.3 Immutable approved records



Approved records are locked. Authorized reopening creates a new version and preserves the original.



\### 6.4 Consistent generated output



Invoices, contracts, certificates, commission reports, and financial reports must be generated from controlled database records.



\### 6.5 Auditability



Original data, revisions, approvals, signatures, documents, access attempts, payments, costs, and reports must remain auditable.



\### 6.6 Least-privilege access



Each user receives only the access needed for their role. Access applies at the screen, record, field, and action levels.



\---



\## 7. User Roles



\### 7.1 Sales Associate



May:



\- Create customers

\- Create Master Sales Records

\- Create project records

\- Enter and update unapproved project information

\- Review generated contracts

\- Send contracts to customers

\- View assigned customer and project information

\- View commission information related only to their own sales



May not:



\- Approve sales or contracts

\- Edit approved Master Sales Records

\- Change approved retail price

\- Change approved costs

\- View another Sales Associate’s commissions

\- Approve payroll or commission reports

\- Approve financial reports



\### 7.2 Sales Manager



May:



\- Review and approve Master Sales Records

\- Enter or confirm retail prices

\- Sign contracts and invoices

\- Approve payment credits, refunds, and adjustments

\- Enter overhead expenses

\- Enter or revise permitted costs

\- Reopen approved records

\- Approve commission changes

\- Approve payroll or commission reports

\- Approve and sign published financial statements

\- View all business data

\- View the tamper-evident audit log

\- Manage selected operational exceptions



\### 7.3 Comptroller



May:



\- Review and approve Master Sales Records

\- Enter or confirm retail prices

\- Sign contracts and invoices

\- Sign certificates only when the Installation Manager is unavailable

\- Enter overhead expenses

\- Enter or revise permitted costs

\- Reopen approved records

\- Approve commission changes

\- Approve payroll or commission reports

\- Approve and sign published financial statements

\- View all business data

\- View the tamper-evident audit log

\- Manage financial and accounting functions



\### 7.4 Installation Manager



May:



\- Schedule installation tasks

\- View installation-related projects

\- Review installation status

\- Enter or approve installation-related cost information

\- Sign certificates

\- View change history

\- Access the tamper-evident audit log

\- View assigned or authorized project information



The Installation Manager does not sign financial statements.



\### 7.5 Technician



May:



\- View assigned projects

\- View approved scope of work

\- Update equipment serial numbers

\- Record installation completion

\- Record actual materials used

\- Enter completion notes

\- Record proposed scope changes

\- Review and send certificates to customers



May not:



\- Change retail price

\- Change approved costs

\- Change contract terms

\- Approve sales

\- Approve contracts

\- Approve financial reports

\- View unauthorized commissions, payroll, or financial information



\### 7.6 Accounts Payable Associate



May:



\- View authorized vendor and payable records

\- Enter payable payments

\- Update payable status

\- Record payment dates and methods

\- View related project information necessary for accounts-payable duties



\### 7.7 Database Administrator



May:



\- Search authorized records

\- Maintain database records according to assigned permissions

\- Maintain data quality

\- Administer approved database functions



May not automatically approve sales, commissions, payroll, or financial reports unless separately assigned that authorization.



\### 7.8 Other Contractors



May:



\- View only projects and tasks specifically assigned to them

\- View only the fields required to complete their assigned work



\---



\## 8. Core Data Entities



The system should use a relational database with linked entities.



\### 8.1 Customer



Fields include:



\- Customer ID

\- Customer name

\- Multiple phone numbers

\- Multiple email addresses

\- Mailing address, if required

\- Customer status

\- Customer folder reference

\- Creation date

\- Last modified date

\- Duplicate-check information



\### 8.2 Customer Contact



Fields include:



\- Contact ID

\- Customer ID

\- Contact name

\- Contact type

\- Phone number

\- Email address

\- Primary contact indicator

\- Preferred contact method

\- Active or inactive status



\### 8.3 Project



Fields include:



\- Project ID

\- Customer ID

\- Project identification code

\- Project location

\- Assigned Sales Associate

\- Assigned Technician or Technicians

\- Scope of work

\- Project status

\- Creation date

\- Completion date

\- Cancellation status

\- Current Master Sales Record version



A customer may have multiple projects.



A single Master Sales Record exists for each project location and project scope.



\### 8.4 Project Location



Separate fields are required for:



\- Street address

\- City

\- State

\- ZIP code



The project location’s state determines the default license artwork.



\### 8.5 Master Sales Record



Fields include:



\- Master Sales Record ID

\- Project ID

\- Customer ID

\- Version number

\- Creation date

\- Created by

\- Assigned Sales Associate

\- Retail price

\- Payment option

\- Scope of work

\- Equipment

\- Serial numbers

\- Material costs

\- Equipment costs

\- Dealer fees

\- Lead cost

\- Technician Cost

\- Damon cost

\- Jerry cost

\- Contract data

\- Invoice data

\- Certificate data

\- Approval status

\- Document version references

\- Revision reason

\- Revision date and time

\- User making revision



The Master Sales Record is the authoritative source for project information.



\### 8.6 Equipment



Multiple equipment records may be associated with one project.



Fields include:



\- Equipment ID

\- Project ID

\- Brand

\- Model

\- Function

\- Serial number

\- Equipment category

\- New, existing, removed, or installed status

\- Inventory reference

\- Notes



\### 8.7 Invoice



Fields include:



\- Invoice ID

\- Invoice number

\- Project identification code

\- Master Sales Record version

\- Invoice amount

\- Payment option

\- Adjustment amount

\- Adjusted amount due

\- GECC signer

\- GECC signature date

\- Customer signer

\- Customer signature date

\- Invoice status

\- PDF version

\- Signature audit certificate

\- File location



The invoice number equals the unique project identification code.



\### 8.8 Contract



The contract is an existing PDF template provided by GECC.



Fields include:



\- Contract ID

\- Project ID

\- Master Sales Record version

\- Template version

\- Customer signer

\- Customer signature date

\- GECC signer

\- GECC signature date

\- Contract status

\- PDF version

\- Signature audit certificate

\- File location



\### 8.9 Certificate



The certificate is an existing PDF template provided by GECC.



Fields include:



\- Certificate ID

\- Project ID

\- Master Sales Record version

\- Template version

\- Customer signer

\- Customer signature date

\- Installation Manager signer

\- Installation Manager signature date

\- Comptroller substitute signer, if applicable

\- Substitute-signature reason

\- Certificate status

\- PDF version

\- Signature audit certificate

\- File location



\### 8.10 Payment



Fields include:



\- Payment ID

\- Project ID

\- Invoice ID

\- Project identification code

\- Payment method

\- Amount

\- Payment date

\- Received date

\- Verification date

\- Verification status

\- Cashier’s check number

\- Bank name

\- Bank-wire reference number

\- Uploaded proof of receipt

\- User entering payment

\- Notes

\- Adjustment reference



Supported initial payment methods:



\- Bank cashier’s check

\- Bank wire transfer



\### 8.11 Accounts Receivable



Accounts receivable must track:



\- Invoice amount

\- Amount paid

\- Approved credits

\- Approved refunds

\- Approved adjustments

\- Remaining balance

\- Payment status

\- Verification status

\- Project identification code

\- Customer

\- Invoice



Unpaid invoices remain visible as accounts receivable.



Revenue and profit are recognized only when cash is received, subject to the final accounting implementation and review.



\### 8.12 Contractor or Employee



Fields include:



\- Contractor or employee ID

\- Name

\- Address

\- Email

\- Phone

\- Role

\- Independent-contractor status

\- Active or inactive status

\- Commission configuration

\- Assigned projects

\- Payment history



\### 8.13 Overhead Expense



Fields include:



\- Expense ID

\- Date

\- Amount

\- Expense category

\- Required description

\- Vendor

\- Payment status

\- User entering expense

\- Project association, if applicable

\- Approval status

\- Notes



Only the Sales Manager and Comptroller may enter overhead expenses.



\### 8.14 Accounts Payable



Separate payables must be created for:



\- Equipment

\- Dealer fees

\- Materials



Fields include:



\- Payable ID

\- Project ID

\- Vendor

\- Payable category

\- Description

\- Amount owed

\- Certificate signing date

\- Payable creation date

\- Due date

\- Payment date

\- Payment method

\- Amount paid

\- Outstanding balance

\- Payment status

\- Notes

\- Approval history



Accounts payable is created on the Certificate signing date even if GECC has not paid the vendor.



\### 8.15 Inventory



Inventory is tracked on a First In, First Out basis.



Fields include:



\- Inventory ID

\- Serial number

\- Brand

\- Model

\- Function

\- Product type

\- Acquisition date

\- Acquisition cost

\- Vendor

\- Project allocation

\- Inventory status

\- Date issued

\- Cost layer



FIFO should be tracked by product identity and cost layer. Serial-number records must remain individually identifiable.



\### 8.16 Fixed Asset



Initial fixed-asset categories:



\- Vehicles

\- Computers

\- Offices



Vehicle fields include:



\- VIN

\- Description

\- Acquisition date

\- Cost

\- Placed-in-service date

\- Useful life

\- Accumulated depreciation

\- Net book value

\- Disposal information



Computer fields include:



\- Serial number

\- Description

\- Acquisition date

\- Cost

\- Placed-in-service date

\- Useful life

\- Accumulated depreciation

\- Net book value

\- Disposal information



Office fields include:



\- Address

\- Description

\- Acquisition date

\- Cost

\- Placed-in-service date

\- Useful life

\- Accumulated depreciation

\- Net book value

\- Disposal information



Additional asset categories may be created with:



\- Category name

\- Identifying code

\- Description

\- Acquisition date

\- Cost

\- Placed-in-service date

\- Useful life

\- Depreciation data



Depreciation method is always straight-line.



Depreciation begins on the placed-in-service date.



\### 8.17 Loan



Fields include:



\- Loan ID

\- Lender

\- Loan amount

\- Loan date

\- Term

\- Interest rate

\- Payment schedule

\- Principal balance

\- Interest paid

\- Loan status

\- Notes



\### 8.18 Financial-Report Period



Fields include:



\- Period ID

\- Month

\- Year

\- Period start date

\- Period end date

\- Report preparation date

\- Report publication date

\- Approval status

\- Signature status

\- Locked status

\- Adjustment references



Monthly financial reports are prepared on the fifth calendar day of the following month.



Example:



\- May reports are prepared on June 5.



Once published, the period is locked. Corrections require formal adjustment entries.



\---



\## 9. Project Identification Code



Users enter the Sales Associate initials, while the system automatically generates the sequential number.



The code format is:



```text

Sequential Number-Sales Associate Initials-Master Sales Record Creation Date

The sequence begins at 101.



The date format is:



text





YYYY-MM-DD

Example:



text





101-JD-2026-09-19

The system must:



Generate the sequential number automatically

Prevent duplicate project codes

Reserve the number during record creation

Prevent reuse of cancelled project codes

Use the Master Sales Record creation date

Preserve the original code through revisions

Warn about an existing active project at the same customer location

Require an explanation or correction before allowing another active project at that location

10\. Scope of Work

The system must allow multiple scope selections:



Service

Repair

Install new

Remove old

Under Install New and Remove Old, users may select multiple items:



Condenser coil

Evaporator coil

Refrigerant

Air handler

Furnace

Thermostat

Air ducts

Vents

Service, repair, removal, and installation use the same general workflow.



A project may include multiple pieces of equipment and multiple serial numbers.



11\. Approved Controlled Lifecycle

Step 1 — Create Master Sales Record

The Sales Associate interviews the customer and creates the Master Sales Record for the customer’s project.



Step 2 — Review and approve

The Sales Manager or Comptroller:



Reviews the record

Enters or confirms the retail price

Approves the Master Sales Record

Both do not need to approve. One authorized approval is sufficient.



Step 3 — Generate documents

After Master Sales Record approval, the system generates:



Invoice

Contract

Certificate

All documents must use the approved Master Sales Record.



Step 4 — Review contract

The Sales Associate reviews the generated contract to ensure that the inserted information is correct.



Step 5 — Customer signs contract

The customer signs and dates the contract first.



Step 6 — GECC signs contract

Either the Sales Manager or Comptroller signs and dates the contract for GECC.



Both do not need to sign.



Step 7 — Send invoice after contract signing

The invoice is generated after Master Sales Record approval, but it is sent for signature only after the contract has been signed.



Step 8 — GECC signs invoice

Either the Sales Manager or Comptroller signs and dates the invoice first.



Step 9 — Customer signs invoice

The customer signs and dates the invoice after the GECC signature.



Step 10 — Create installation task

After both the contract and invoice have all required signatures, the system creates an Installation Manager scheduling task.



Step 11 — Enforce waiting period

Installation may not occur earlier than three days after the customer signs both the contract and invoice.



The system must prevent an earlier installation date unless an authorized exception process is later approved.



Step 12 — Perform scope of work

The Technician performs the approved scope of work and records completion data.



The Technician may update:



Equipment serial numbers

Installation completion

Actual materials used

Completion notes

Proposed scope changes

The Technician may not change:



Retail price

Approved costs

Contract terms

Step 13 — Send certificate

The Technician reviews the populated certificate and sends it to the customer.



Step 14 — Customer signs certificate

The customer signs and dates the certificate.



Step 15 — GECC signs certificate

The Installation Manager signs the certificate.



The Comptroller may sign only when the Installation Manager is unavailable. The Comptroller must record the reason for serving as substitute signer.



Step 16 — Receive payment

The customer pays by:



Bank cashier’s check

Bank wire transfer

Step 17 — Verify cashier’s check

A cashier’s check is recognized as received only after the bank confirms the funds.



Step 18 — Record bank wire

Bank wires are manually recorded during the initial implementation.



Before a bank wire is marked verified, the system must require either:



A manually entered wire reference number, or

Uploaded proof of receipt

Step 19 — Apply approved adjustments

Approved credits, refunds, and adjustments may reduce the amount required for completion.



The Sales Manager must approve any adjustment.



The system must preserve:



Original invoice amount

Adjustment amount

Adjusted amount due

Reason

Approver

Date and time

Step 20 — Mark project complete

The project becomes complete only when:



Scope of work is complete

Contract has all required signatures

Certificate has all required signatures

Invoice has all required signatures

Invoice is fully paid after approved adjustments

Payment verification is complete

Step 21 — Earn commissions

Fixed and variable commissions become earned only after project completion.



Step 22 — Create commission reports

The system includes completed projects in the applicable biweekly commission reports.



Step 23 — Approve commission reports

The Sales Manager and Comptroller review and approve commission reports according to the approved commission-report workflow.



Step 24 — Distribute and retain commission reports

Approved commission reports are:



Sent by email to contractors

Retained permanently

Linked to the relevant projects and commission records

12\. Scope-Change Workflow

If a Technician identifies a scope change:



Technician records the proposed change and notes.

Project enters a scope-change-pending state.

Sales Manager or Comptroller reviews the change.

Authorized user approves or rejects the change.

Authorized user enters or approves revised price and costs.

System creates a new Master Sales Record version.

System generates revised documents as required.

Revised contract is sent through a new signature sequence.

Original documents remain permanently preserved.

Work on the changed scope cannot continue until required approvals and signatures are complete.

13\. Document Versioning

When an approved or signed project is revised:



Original Master Sales Record remains permanently preserved.

Original invoice, contract, and certificate remain permanently preserved.

Revised Master Sales Record receives a new version number.

Revised documents receive new version numbers.

Revision includes user, date, time, and reason.

Revised documents are sent through the required new signature sequence.

Original signature audit records remain attached to original documents.

Revised documents are clearly marked as current or superseding versions.

All document versions remain in the customer/project file.

Generated documents must not be independently edited in a way that changes the underlying project data.



14\. Document Generation

The system must generate documents from the approved Master Sales Record.



Each form should allow authorized users to:



Save data to the database

Generate a document

Save the document to the customer/project file

Print the document

Email the document

Send the document for electronic signature

Clear the form for a new entry

Before generation, the system must validate:



Required fields

Customer consistency

Project consistency

Project-code consistency

Pricing consistency

Scope consistency

Equipment and serial-number requirements

Required signature fields

State-specific license artwork

Document version references

15\. Company Logo and License Artwork

Invoices, contracts, and certificates must support:



GECC company logo

State-specific license artwork

Artwork requirements:



Upload Base64 artwork

Validate approved image format

Associate artwork with a state

Set effective date

Activate or retire artwork versions

Preview before activation

Preserve artwork version used in each document

License artwork is selected automatically based on the project location’s state.



An authorized user may override automatic state selection only by:



Selecting alternate artwork

Entering an approval reason

Receiving approval from the Sales Manager or Comptroller

Creating an audit-log entry

The system must stop document generation if required artwork is missing or an override lacks required approval.



Each generated document must retain:



Selected state

Artwork version

Artwork effective date

User who uploaded or changed the artwork

Date and time artwork was used

16\. Electronic Signature System

The built-in signature system must support:



Email delivery

Signature links

Signing order

Customer authentication

Signer authentication

Automatic reminders

Seven-day reminder interval

Seventy-five-day expiration

Signature audit trail

Completed-document certificates

Downloadable signed PDFs

Signature status tracking

Delivery status tracking

Expired-request handling

Unsigned invoices, contracts, and certificates expire after 75 days.



Upon expiration:



Signature request is marked expired.

Sales Manager and Comptroller receive an action task.

Original request remains preserved.

Authorized user may resend, revise, cancel, or extend the request.

Reminder and expiration events remain in the audit trail.

17\. Cost and Profitability Rules

17.1 Gross Profit

text





Gross Profit =

Invoice Amount

\- Equipment Cost

\- Material Cost

\- Dealer Fee

\- Lead Cost

\- Technician Cost

\- Damon Cost

\- Jerry Cost

17.2 Cost permissions

Equipment Cost, Material Cost, and Dealer Fee may be entered by:



Sales Manager

Installation Manager

Comptroller

Technician Cost is a variable actual project cost and may be entered by:



Sales Manager

Installation Manager

Lead Cost, Damon Cost, and Jerry Cost may be edited for an individual project by authorized users.



17.3 Default fixed deductions

Initial default values:



Lead: $3,000

Damon: $500

Jerry: $250

Damon and Jerry are contractors. Their fixed costs are deducted from every project whether or not they were involved.



If a fixed deduction changes, the change applies only to the indicated project. It does not automatically change past, future, or other projects.



17.4 Variable commissions

Ryan:



text





Ryan Commission = 15% × Gross Profit

Doug:



text





Doug Commission = 5% × Gross Profit

If Gross Profit is zero or negative:



No variable commission is paid.

Negative profitability is preserved in reporting.

If Net Profit is zero or negative:



No variable commission is paid.

Negative profitability is preserved in reporting.

17.5 Net Profit

text





Net Profit =

Gross Profit

\- Ryan Commission

\- Doug Commission

Net Profit is split:



50% to the Sales Associate who created and owns the Master Sales Record

50% to GECC

17.6 Fixed compensation

Fixed compensation is paid once per completed project to:



Lead

Damon

Jerry

17.7 Commission eligibility

Commissions are earned only after:



Scope is complete

Certificate is fully signed

Invoice is fully paid after approved adjustments

Project is complete

Only the Sales Manager may approve:



Early commission payment

Commission changes

Commission changes caused by corrected project costs

Commission adjustments after payroll approval

If project cost is corrected after payroll approval:



Create an adjustment in the next payroll period.

Include an adjustment note.

Preserve the original commission report.

Link the adjustment to the original project and payroll period.

18\. Contractor Commission Reports

All workers are independent contractors.



Contractor reports are created every two weeks.



Example:



Pay period: May 1 through May 14

Report date: May 15

Report reviewed by Sales Manager and Comptroller

Report approved

Report emailed to applicable contractors

Approved copy permanently retained

Each contractor’s report includes only their authorized commission information.



Sales Associates may see only commission information related to their own sales.



Every January 5, the system sends each contractor employed during the prior year:



Annual commission summary

Commission payment dates

Commission amounts

Copy of each individual biweekly commission report

19\. Payment and Accounting Rules

Payment methods:



Bank cashier’s check

Bank wire transfer

Payment records must be allocated to the specific customer project using the project identification code.



Unpaid invoices remain visible as accounts receivable.



Revenue and profit are recognized only when cash is received.



Future implementation may add:



Bank-statement import

Bank reconciliation

Automatic transaction matching

Accounts payable is created when the Certificate is signed, even if the payable has not been paid.



Separate payables are required for:



Equipment

Dealer fees

Materials

20\. Financial Reporting

The system must generate:



Balance sheet

Cash-flow statement

Statement of operations

Accounts receivable report

Accounts payable report

Inventory report

Depreciation report

Loan report

Fixed-asset report

Retained earnings report

Working Capital Requirement report

Customer profitability report

Project profitability report

Contractor commission reports

Financial reporting is cash-basis.



Financial reports are prepared on the fifth calendar day of the following month.



Example:



May report date: June 5

Published financial statements must be approved and signed by:



Sales Manager

Comptroller

The Installation Manager does not sign financial statements.



After publication:



The financial period is locked.

Ordinary edits are prevented.

Corrections require formal adjustment entries.

Original published statements remain preserved.

21\. Financial Signatures

Master Sales Record

The Sales Manager, Comptroller, or Installation Manager may approve the Master Sales Record according to the applicable workflow.



Contract

Either the Sales Manager or Comptroller may sign for GECC.



Invoice

Either the Sales Manager or Comptroller may sign for GECC.



The customer signs after GECC signs.



Certificate

The Installation Manager signs.



The Comptroller may sign only when the Installation Manager is unavailable and must record the reason.



The customer signs before the authorized GECC signer.



Commission reports

Sales Manager and Comptroller review and approve commission reports.



Published financial statements

Sales Manager and Comptroller approve and sign published financial statements.



22\. Activity Dashboard

Create an activity dashboard viewable by:



Sales Manager

Comptroller

Installation Manager

Technicians

Sales Associates

Other authorized Contractors

Dashboard access remains permission-based.



Recommended dashboard fields:



Project identification code

Customer name

Project location

Assigned Sales Associate

Assigned Technician

Current project status

Current task

Assigned role or user

Contract status

Invoice status

Certificate status

Installation status

Payment status

Commission status

Next required action

Due date

Days in current status

Last activity date and time

Warning or exception indicator

Dashboard filters:



Status

Customer

Project code

Location

State

Sales Associate

Technician

Date range

Payment status

Signature status

Overdue tasks

Expiring documents

Negative-profit projects

Projects requiring action

Financial amounts, commissions, profitability, and payroll information must not appear to users without authorization.



23\. Search Requirements

Authorized users should be able to search by:



Customer name

Phone number

Email address

Project identification code

Street address

City

State

ZIP code

Sales Associate

Technician

Serial number

Brand

Model

Project status

Contract status

Invoice status

Certificate status

Payment status

Vendor

Payable

Document type

Date range

Search results must respect role-based access restrictions.



24\. Authentication and Access Logging

The system must require authenticated login.



The system must log access to:



Dashboard

Database

Master Sales Record

Customer records

Project records

Documents

Financial reports

Commission reports

Administrative configuration

Each access event must record:



User identity

User role

Date and time

Record or screen accessed

Activity type

Related record identifier

Success or failure

Session identifier

Reason when required

Previous audit-log entry reference

Integrity hash or equivalent value

The system must log:



Successful logins

Failed login attempts

Logout

Views

Searches

Creates

Edits

Approvals

Exports

Prints

Downloads

Emails

Signatures

Permission failures

Attempts to access restricted information

Administrative changes

Users must not be able to edit or delete audit records through the application.



25\. Tamper-Evident Audit Log

The audit log must be separate from ordinary business records.



It must be:



Append-only

Read-only to ordinary users

Tamper-evident

Searchable

Exportable

Protected from normal application edits and deletion

Each log entry references the preceding entry to create a chain.



An alteration, deletion, insertion, or reordering of audit entries should cause an integrity verification failure.



Audit-log access is limited to:



Sales Manager

Comptroller

Installation Manager

26\. Form Functions

Authorized forms should support:



Save to database

Save as draft

Generate document

Save document to customer/project file

Print

Email

Send for signature

Clear form

Cancel form

Reopen authorized record

Create new record

Forms must validate data before saving or generating documents.



27\. Validation and Error Prevention

The system must prevent:



Duplicate project codes

Invalid project-code format

Duplicate active project locations without explanation

Missing required fields

Unauthorized changes

Installation before the waiting period

Document generation from incomplete data

Contract, invoice, and certificate data mismatches

Unverified payment being treated as received

Commission before project completion

Variable commission on zero or negative profitability

Period edits after financial statements are published

State-artwork omission

Unauthorized artwork override

Document generation without required approvals

28\. Exception Dashboard

The system should flag:



Contracts awaiting customer signature

Contracts awaiting GECC signature

Invoices awaiting GECC signature

Invoices awaiting customer signature

Certificates awaiting customer signature

Certificates awaiting Installation Manager signature

Signature requests nearing expiration

Expired signature requests

Installations awaiting scheduling

Installation dates violating the three-day rule

Projects with completed work but no payment

Unpaid invoices

Unverified cashier’s checks

Unverified bank wires

Scope changes awaiting approval

Negative-profit projects

Missing equipment serial numbers

Commission adjustments awaiting approval

Payables past due

Financial reports awaiting approval

Closed-period adjustment requests

29\. Data Integrity and Versioning

The system should use:



Relational database constraints

Foreign keys

Required-field validation

Unique indexes

Controlled enumerated values

Immutable document versions

Versioned Master Sales Records

Append-only audit entries

Transactional saves

Duplicate detection

Status-transition validation

Consistency checks before document generation

The database is the authoritative system of record.



PDFs, emails, exports, and Google Sheets are generated copies or outputs.



30\. Recommended Accounting Architecture

The system should use a double-entry accounting ledger internally, even though reporting is cash-basis.



The ledger should support:



Accounts

Debits

Credits

Journal entries

Cash receipts

Cash disbursements

Accounts receivable tracking

Accounts payable tracking

Inventory

Fixed assets

Depreciation

Loans

Retained earnings

Period close

Adjusting entries

Final accounting treatment should be validated during the financial-reporting sprint.



31\. Recommended Sprint Plan

Sprint 00 — Project Baseline and Architecture

Deliver:



Approved requirements

Roles and permissions

Lifecycle

Business rules

Architecture assumptions

Acceptance criteria

Initial backlog

Sprint 01 — Database Model and Accounting Foundation

Deliver:



Relational schema

Core entities

Relationships

Constraints

Versioning model

Accounting foundation

Sprint 02 — Authentication, Roles, and Permissions

Deliver:



Login

Role model

Record permissions

Field permissions

Commission visibility controls

Session rules

Sprint 03 — Tamper-Evident Audit Logging

Deliver:



Append-only audit model

Hash-chain design

Access logging

Restricted-access logging

Verification process

Sprint 04 — Customers, Contacts, Locations, and Projects

Deliver:



Customer records

Multiple contacts

Locations

Duplicate detection

Project code generation

Search

Sprint 05 — Master Sales Record

Deliver:



Master Sales Record form

Scope selections

Equipment

Serial numbers

Pricing

Costs

Payment options

Draft and approved versions

Sprint 06 — Controlled Lifecycle and Task Workflow

Deliver:



State machine

Approval tasks

Installation tasks

Three-day restriction

Scope-change process

Reopen and revision process

Sprint 07 — Document Generation and Artwork

Deliver:



Invoice generation

Contract population

Certificate population

Logo

State license artwork

Base64 validation

Artwork override process

Sprint 08 — Electronic Signatures and Reminders

Deliver:



Signature requests

Signing order

Authentication

Reminders

Expiration

Audit certificates

Signed PDFs

Sprint 09 — Payments, Receivables, Payables, and Adjustments

Deliver:



Cashier’s check

Bank wire

Verification

Payment allocation

Credits

Refunds

Separate payables

Sprint 10 — Costs, Profitability, Commissions, and Contractor Reports

Deliver:



Cost rules

Gross Profit

Net Profit

Fixed compensation

Variable commissions

Commission adjustments

Biweekly reports

Annual summaries

Sprint 11 — Inventory, Assets, Loans, and Depreciation

Deliver:



FIFO inventory

Serial-number tracking

Fixed assets

Straight-line depreciation

Loans

Asset reports

Sprint 12 — Financial Ledger and Reporting

Deliver:



Double-entry ledger

Cash-basis reports

Balance sheet

Cash-flow statement

Statement of operations

Working Capital Requirement

Period close

Sprint 13 — Activity Dashboard and Search

Deliver:



Activity dashboard

Role-specific views

Filters

Exceptions

Project search

Commission visibility

Sprint 14 — Notifications, Email, and File Management

Deliver:



Notifications

Email delivery

Customer/project folders

Delivery audit records

Annual report email process

Sprint 15 — Testing, Security, and Data Integrity

Deliver:



End-to-end testing

Permission testing

Audit testing

Document consistency testing

Financial testing

Backup and restore testing

Sprint 16 — Deployment, Migration, and Operations

Deliver:



Deployment instructions

Initial-user setup

Data migration plan

Backup procedures

Recovery procedures

Administrator guide

User guides

Release checklist

32\. Acceptance Criteria

The baseline is accepted when:



The Master Sales Record is the single source of truth.

Users cannot bypass required lifecycle steps.

Unauthorized users cannot view or edit restricted information.

Sales Associates see only their own commission data.

Approved records cannot be silently overwritten.

Revisions preserve previous versions.

Documents use consistent approved data.

State-specific artwork is automatically selected.

Artwork overrides require approval and a reason.

The three-day installation rule is enforced.

Projects cannot be complete before all required signatures and payment conditions are met.

Payments are linked to the correct project code.

Cashier’s checks require bank confirmation.

Bank wires require a reference number or proof of receipt.

Variable commissions are withheld when profitability is zero or negative.

Commission adjustments are preserved and approved.

Financial periods can be closed and corrected through adjustments.

Audit entries are append-only and tamper-evident.

Restricted-access attempts are logged.

The activity dashboard shows current project status and required actions.

Reports are searchable and reproducible.

Customer/project files preserve all required documents and versions.

33\. Open Implementation Items

The following items require inputs or configuration during later sprints:



Existing contract PDF

Existing certificate PDF

Invoice layout and field placement

GECC logo artwork

State-specific license artwork

Exact document signature placement

Electronic-signature authentication method

Accounting chart of accounts

Asset useful lives by category

Vendor master list

Existing customer and project data

Email delivery configuration

User list and role assignments

Contractor payment-report formatting

Financial-report distribution list

Final accounting treatment of accounts payable and cash-basis reporting

34\. Known Risks

Existing PDFs may not be fillable or may require specialized PDF-overlay processing.

Electronic-signature requirements may require additional legal and technical validation.

Incorrect cost configuration could produce incorrect profitability and commission results.

Cashier’s-check verification may remain manual until bank integration is implemented.

Financial reporting requires a carefully configured chart of accounts.

Existing spreadsheet data may contain duplicates or inconsistent values.

State license artwork may change and require version management.

Large audit logs may require archival and integrity-verification procedures.

35\. Merge Instructions

This bundle is the baseline project context.



When a later bundle is created:



Preserve this file unchanged.

Create the next bundle using the next sprint number.

Record all new decisions and changes.

If a later decision conflicts with this baseline, the later approved decision supersedes the earlier one.

Preserve the superseded requirement in the historical record.

Do not silently delete prior requirements.

Append bundles in sprint order to create the master file.

Master file name:



text





GECC-master-project-bundle.md

Recommended bundle order:



text





GECC-00-project-baseline.md

GECC-01-data-model.md

GECC-02-auth-and-permissions.md

GECC-03-audit-log.md

GECC-04-customers-and-projects.md

GECC-05-master-sales-record.md

GECC-06-workflow-state-machine.md

GECC-07-document-generation.md

GECC-08-electronic-signatures.md

GECC-09-payments-and-payables.md

GECC-10-costs-and-commissions.md

GECC-11-inventory-assets-and-loans.md

GECC-12-financial-reporting.md

GECC-13-dashboard-and-search.md

GECC-14-notifications-and-files.md

GECC-15-testing-and-integrity.md

GECC-16-deployment-and-operations.md

36\. Next Sprint

Sprint number: 01

Sprint name: Database Model and Accounting Foundation

Objective: Convert this approved baseline into a detailed relational database schema and accounting foundation.

Required inputs:

No additional business requirements required to begin

Existing documents may be deferred until Sprint 07

Expected deliverables:

Entity relationship model

Table definitions

Field definitions

Keys and relationships

Constraints

Versioning structure

Audit references

Initial accounting data model

Database acceptance tests

