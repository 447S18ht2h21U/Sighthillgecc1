# VERIDIAN Local Deployment Implementation Plan â€” Version 1

## 1. Document Control

Project: VERIDIAN
Organization: GECC
Document Version: 1.0
Status: Controlled Draft â€” Implementation Planning
Date: October 13, 2026
Related Decision: VERIDIAN-Local-Hosting-Architecture-Decision-v1.md

## 2. Purpose

This document defines the proposed implementation approach for deploying VERIDIAN on GECC-owned local infrastructure.

The plan replaces AWS-first deployment planning as the active infrastructure implementation direction. AWS deployment remains deferred until GECC authorizes reconsideration.

This document does not authorize production operation.

## 3. Approved Deployment Principles

1. GECC-owned infrastructure is the preferred initial production hosting platform.
2. Production availability is required from 8:00 AM through 8:00 PM Eastern Time.
3. Secure remote access must be supported.
4. Local backup capability is mandatory.
5. N+1 server power-supply redundancy remains a requirement unless GECC explicitly approves a documented exception.
6. UPS and generator arrangements must be validated against the selected hardware and network equipment.
7. The approved Recovery Point Objective is zero data loss.
8. The approved Recovery Time Objective is 15 minutes.
9. Development, staging, and production must remain appropriately separated.
10. Production credentials, database contents, and customer documents must be protected.
11. All production deployment and recovery procedures must be documented and tested.
12. Hardware procurement and production launch require separate approval.

## 4. Implementation Status

Hosting direction: Approved
Hardware selection: Pending
UPS selection: Pending
Network architecture: Pending
Backup and recovery architecture: Pending
Production identity integration: Pending
Staging validation: Pending
Production authorization: Not granted

## 5. Local Production Technical Architecture

### 5.1 Proposed Operating Platform

- Operating system: Ubuntu 24.04 LTS.
- Application framework: Django 5.2.
- Database: PostgreSQL.
- Frontend: Production-built VERIDIAN web application.
- Application runtime: Supported Python environment with production WSGI/ASGI service.
- Reverse proxy: Nginx or another approved production reverse proxy.
- Service management: systemd or an approved container deployment approach.
- Document storage: Protected persistent storage.
- Background processing: Managed services where required.

Final software versions and deployment configuration must be verified against the application repository.

### 5.2 Proposed Application Request Path

1. An authorized user connects through the approved secure remote-access solution or trusted local network.
2. HTTPS traffic reaches the approved reverse proxy.
3. The reverse proxy serves the frontend and routes application requests to Django.
4. Django enforces authentication, authorization, business rules, and audit controls.
5. PostgreSQL stores application records and transactional data.
6. Protected document storage holds generated and uploaded business documents.

PostgreSQL and internal application services must not be directly exposed to the public internet.

The final network design must define TLS certificates, DNS, firewall rules, access controls, and remote-access authentication.

### 5.3 Production Service Isolation

- Production must use its own PostgreSQL database, credentials, document storage, and configuration.
- Development and staging must not share production secrets or writable production data.
- Production secrets must never be committed to Git or included in application logs.
- Administrative access must be restricted to authorized personnel and protected by strong authentication.
- Database access must be limited to authorized application services and designated administrators.
- Production debugging, development-only authentication, and test bootstrap mechanisms must be disabled.
- Production services must operate with least-privilege operating-system and database permissions.
- Firewall rules must restrict access to application, database, and management interfaces.
- Security-relevant administrative actions must be logged and reviewed.
- Configuration changes must follow the approved authorization and audit requirements.

The final implementation must verify these controls before production authorization.

### 5.4 Data and Storage Protection

- Production PostgreSQL data must reside on protected persistent storage.
- Mirrored SSD storage is preferred to reduce exposure to individual drive failures.
- RAID 1 or equivalent mirroring does not replace independent backups.
- Production documents must be stored in protected persistent storage with restricted access.
- Database and document backups must be coordinated to support consistent recovery.
- A separate local backup device is required; internal server drives alone are insufficient.
- Backup storage must be protected against unauthorized modification and deletion.
- Backup encryption, retention periods, and storage capacity require approval.
- PostgreSQL point-in-time recovery and transaction-log archiving must be evaluated.
- Backup integrity checks and scheduled restoration tests are mandatory.
- Backup failures must generate actionable alerts.
- Recovery procedures must include database, document, configuration, and application restoration.

The approved zero-data-loss RPO and 15-minute RTO remain unverified until recovery testing demonstrates compliance for the defined failure scenarios.

### 5.5 Availability and Recovery Constraints

- Required production availability is 8:00 AM through 8:00 PM Eastern Time.
- The initial architecture assumes one GECC-owned production server.
- GECC has an existing 17 kW natural gas generator intended to restore electrical supply following utility failure.
- A UPS must maintain uninterrupted power during generator startup and transfer.
- UPS runtime must be validated against the actual server and network-equipment electrical load.
- The proposed UPS design should initially target at least 15 to 20 minutes of runtime at the measured load.
- Generator startup, automatic transfer, and recovery behavior must be tested.
- Network equipment required for local and remote access must also receive protected power.
- N+1 internal server power-supply redundancy remains a requirement unless GECC approves a documented exception.
- Mirrored drives reduce exposure to individual storage-device failures but do not provide server-level redundancy.
- A single-server architecture remains vulnerable to motherboard, processor, controller, and other critical hardware failures.
- Recovery procedures must account for hardware replacement, application restoration, database recovery, and document restoration.
- The 15-minute RTO and zero-data-loss RPO cannot be considered satisfied without evidence from representative recovery tests.
- Any recovery limitation that cannot be eliminated must be documented and presented to GECC for an explicit risk decision.

Production operation remains unauthorized until the required availability, recovery, and security controls have been evaluated.

### 5.6 Implementation Boundary

This section defines the proposed local production architecture and its required controls.

- No production server has been purchased or commissioned.
- No production database or application services have been deployed.
- No production remote-access gateway has been configured or validated.
- No production backup or recovery system has been commissioned.
- No UPS configuration or generator transfer test has been approved for VERIDIAN.
- No production identity integration has been completed or validated.
- No staging acceptance or production recovery testing has been completed.
- No production launch authorization has been granted.

Implementation evidence must be recorded separately from architecture plans.

GECC must approve hardware, security controls, recovery arrangements, and production readiness before VERIDIAN enters live operation.

## 6. Network Security and Remote Access

### 6.1 Proposed Network Security Architecture

- The VERIDIAN production server must operate behind a properly configured firewall.
- Server addressing must use a static IP address or DHCP reservation.
- Remote access must use an approved encrypted VPN or Zero Trust solution.
- Remote-access authentication must require multifactor authentication.
- Application traffic must use HTTPS with valid TLS certificates.

- PostgreSQL must not be directly accessible from the public internet.
- SSH and server management access must be restricted to authorized administrators.
- Firewall rules must deny traffic by default, allowing only approved exceptions.
- Production systems should be isolated from ordinary user devices where practical.
- Essential network equipment must be included in the UPS power assessment.
- Firewall and remote-access security events must be logged and reviewed.
- Network security updates must follow documented maintenance procedures.

Final firewall, VPN, DNS, TLS, and network configurations require validation before production authorization.

### 6.2 Remote User Access and Authentication

- Remote access must be limited to authorized GECC users with active accounts.
- Each user must have an individual identity; shared accounts are prohibited.
- Remote connections must use the approved VPN or Zero Trust access solution.
- Multifactor authentication must be enforced for remote access.
- VERIDIAN must independently enforce application roles and project permissions.
- Network access must not automatically grant access to every VERIDIAN project.
- Sales and Technical Associates must remain restricted to assigned projects.
- Manager and Comptroller access must follow approved role permissions.

- Account creation and role assignment must require authorized approval.
- User permissions must follow least-privilege principles.
- Remote-access sessions must expire after an approved inactivity period.
- Lost or compromised credentials must be revoked promptly.
- Departing users must have network and application access disabled.
- Role changes must trigger a review of existing permissions.
- Authentication failures and access changes must be logged.
- Privileged access must be reviewed periodically.

Production identity integration and these access controls must be tested before launch.

### 6.3 Remote Access Availability and Operational Controls

- Remote access must support the approved 8:00 AM to 8:00 PM Eastern operating window.
- The internet connection must be assessed for reliability and upload capacity.
- Remote-access equipment must be included in power protection planning.
- Network and remote-access service health must be monitored.
- Loss of internet connectivity must generate an operational alert where feasible.
- Authorized administrators must have a documented network recovery procedure.
- Remote access must fail securely if its authentication service is unavailable.

- Internet outages must be recorded with their duration and operational impact.
- A secondary internet connection may be evaluated but is not yet approved.
- Network recovery procedures must be tested before production launch.
- Remote-access recovery time must be measured during testing.
- The 15-minute recovery objective cannot be guaranteed without supporting evidence.
- Unresolved availability risks must be documented for GECC approval.

No internet redundancy, automatic failover, or recovery capability is assumed to exist until implemented and tested.

### 6.4 Network Security Validation and Acceptance Criteria

- Verify that only approved network ports and services are reachable.
- Confirm PostgreSQL cannot be accessed directly from the public internet.
- Test remote access using an authorized account with multifactor authentication.
- Confirm unauthorized accounts cannot establish remote connections.
- Verify that HTTPS uses a valid certificate and approved TLS configuration.
- Confirm SSH and administrative interfaces are restricted appropriately.
- Test that application permissions remain enforced after remote authentication.

- Verify that network and remote-access security events are logged.
- Test monitoring alerts for network or remote-access service failures.
- Test recovery following a simulated internet connectivity interruption.
- Record measured recovery times and any unmet availability objectives.
- Confirm that firewall, VPN, DNS, and certificate settings are documented.
- Record test results, responsible personnel, and outstanding deficiencies.
- Require GECC approval of unresolved risks before production authorization.

Network security acceptance requires documented evidence, not configuration statements alone.

## 7. Production Identity and Access Management

### 7.1 Production Identity Architecture

- Production authentication must use an approved identity provider.
- The production identity provider has not yet been selected or implemented.
- Development-only authentication must be disabled in production.
- Each employee and contractor must use an individually assigned account.
- Production authentication must enforce approved multifactor authentication controls.
- Identity verification must occur before VERIDIAN grants application access.
- VERIDIAN must enforce its own role and project-access permissions.

### 7.2 Identity Provider Selection and Integration Requirements

- The identity provider must support secure authentication for employees and contractors.
- Multifactor authentication must be available and enforceable.
- The solution must support individual account creation, suspension, and revocation.
- Integration must use established authentication standards such as OIDC or SAML.
- The provider must be compatible with the approved local-hosting architecture.
- Licensing, subscription, and operational costs must be evaluated.
- Provider availability and recovery dependencies must be documented.

- Authentication tokens must be validated for signature, issuer, audience, and expiration.
- Identity integration must use approved secure protocols and configurations.
- Identity provider credentials and secrets must be protected outside source control.
- Account suspension must prevent further application access within an approved interval.
- Provider administrator privileges must be restricted and audited.
- Identity provider selection must receive documented GECC approval.
- Integration testing must be completed before production authorization.

No identity provider is considered selected or production-ready until formally approved and validated.

### 7.3 Role-Based Access Control and Project Permissions

- VERIDIAN must enforce role-based authorization on the server.
- User roles and permissions must follow GECC-approved policies.
- Sales Associates must access only their assigned projects.
- Technical Associates must access only their assigned projects.
- Sales and Installation Managers must access projects within their approved authority.
- The Comptroller must access projects and financial controls within approved authority.
- Access checks must apply to dashboards, records, documents, and API requests.

- Temporary-duty permissions must require independent authorization.
- The Comptroller must authorize the CEO to assume Sales or Installation Manager duties.
- The CEO must authorize the Comptroller to assume those managerial duties.
- Self-approval of temporary-duty authorization is prohibited.
- Each authorization must specify permitted duties and its effective time window.
- Project access scope must be approved separately from temporary-duty authorization.
- Financial allocation must remain independent of temporary-duty permissions.
- Temporary-duty grants, changes, and expiration must be fully audited.

- Approval workflows must enforce GECC-authorized separation of duties.
- Users must not approve their own actions where independent approval is required.
- The Comptroller alone may initiate changes to controlled configuration values.
- Controlled configuration changes must require approval and effective-date tracking.
- Approved Master Sales Records must remain immutable.
- Commercial changes after approval must create a new record version.
- Permission changes and privileged actions must produce attributable audit records.
- Audit records must identify the actor, action, timestamp, and affected record.

Production authorization controls must be validated against approved GECC workflows before launch.

### 7.4 Identity and Authorization Testing

- Verify successful authentication through the approved production identity provider.
- Confirm multifactor authentication is enforced for applicable accounts.
- Confirm invalid, expired, or improperly signed authentication tokens are rejected.
- Verify suspended and revoked accounts cannot establish new sessions.
- Confirm development-only authentication cannot be used in production.
- Test each organizational role against its approved permissions.
- Verify Associates cannot access projects assigned exclusively to other users.

- Verify CEO temporary managerial duties require Comptroller authorization.
- Verify Comptroller temporary managerial duties require CEO authorization.
- Confirm temporary-duty self-approval is prohibited.
- Test authorization start times, expiration, and permitted duties.
- Confirm project access requires separately approved project scope.
- Verify temporary duties do not change financial allocations.
- Test independent approval requirements and prohibited self-approvals.
- Confirm privileged actions and permission changes generate audit records.

- Verify configuration changes require authorized approval and effective-date tracking.
- Confirm approved Master Sales Records cannot be modified directly.
- Verify subsequent commercial changes create a new record version.
- Test account termination and revocation of existing application sessions.
- Record test results, responsible personnel, and unresolved deficiencies.
- Require GECC approval of unresolved identity and authorization risks.

Production identity integration must pass documented acceptance testing before launch.

Section 7 defines required controls; it does not establish that production identity integration has been completed.

## 8. Production Database, Data Protection, and Backup Implementation

### 8.1 Production Database Architecture

- PostgreSQL is the proposed production database platform.
- Production data must be isolated from development and staging databases.
- Database access must use dedicated accounts with least-privilege permissions.
- Database credentials must be stored securely outside source control.
- PostgreSQL must not be exposed directly to the public internet.
- Database storage must use approved persistent storage with appropriate redundancy.
- Database configuration and version changes must follow controlled procedures.

### 8.2 Database Integrity and Transaction Protection

- PostgreSQL transactions must protect related database changes from partial completion.
- Financial and approval workflows must preserve database consistency.
- Database constraints must enforce required relationships and data integrity.
- Approved Master Sales Records must remain immutable under application controls.
- Commercial revisions must create new versions rather than overwrite approved records.
- Audit records must preserve attributable changes and approval history.
- Database write permissions must be restricted to authorized application services.

- PostgreSQL write-ahead logging must remain enabled for transaction recovery.
- Durable commit settings must be reviewed and approved before production use.
- Database storage must support reliable write flushing and crash recovery.
- Transaction failures must roll back incomplete related changes.
- Database shutdown and restart procedures must protect committed records.
- Crash recovery must be tested using representative transaction scenarios.
- Recovery tests must verify financial records, approvals, and audit integrity.

Database durability controls alone do not establish a zero-data-loss recovery capability.

### 8.3 Backup Architecture and Data Protection

- Production backups must be stored separately from the primary server storage.
- Backup storage must remain independently recoverable after a server failure.
- PostgreSQL backups must use a documented, consistent backup method.
- Point-in-time recovery using archived transaction logs must be evaluated.
- Customer documents and generated business records must be included in backups.
- Application configuration needed for recovery must be securely preserved.
- Backup credentials and encryption keys must be protected from unauthorized access.

- Backup frequency must be established based on approved recovery objectives.
- Backup retention periods must be documented and approved by GECC.
- Backup jobs must be automated and monitored for failures.
- Failed or incomplete backups must generate operational alerts.
- Backup integrity must be verified through scheduled restoration tests.
- Restoration tests must include database records and customer documents.
- Backup access must be restricted and all administrative actions audited.

- Backup storage must use security controls independent of production accounts.
- Backup copies must be protected against unauthorized deletion or modification.
- Immutable or offline backup copies must be evaluated for ransomware protection.
- Backup encryption must protect sensitive customer and financial information.
- Recovery keys must be stored securely and remain available during an outage.
- Simultaneous loss of the server and local backup device must be assessed.
- Off-site backup protection must be evaluated against cost and recovery needs.

Backup equipment, protection methods, and off-site arrangements remain subject to GECC approval.

### 8.4 Recovery Objectives and Disaster Recovery Implementation

- GECC has approved a recovery point objective (RPO) of zero data loss.
- GECC has approved a recovery time objective (RTO) of 15 minutes.
- These objectives remain targets until demonstrated through recovery testing.
- A single production server cannot guarantee recovery from every hardware failure.
- Periodic backups alone cannot guarantee zero data loss.
- Recovery planning must address database, documents, configuration, and credentials.
- Recovery procedures must identify responsible personnel and required equipment.

- Mirrored storage may reduce downtime from an individual drive failure.
- A UPS and generator may protect against short power interruptions.
- Independent backups are required for recovery from data loss or corruption.
- PostgreSQL transaction-log archiving may support point-in-time recovery.
- A complete server failure may require replacement hardware and restoration.
- Rapid failover would require additional infrastructure and configuration.
- Recovery equipment and procedures must be evaluated against GECC costs.

- Recovery tests must cover power, storage, database, and server failure scenarios.
- Each test must measure actual data loss and elapsed recovery time.
- Recovery results must be compared against the approved RPO and RTO.
- Failed recovery tests must produce documented corrective actions.
- Unresolved recovery limitations must be presented to GECC leadership.
- Any exception to an approved recovery objective requires explicit authorization.
- Production launch must not imply that unverified recovery objectives are satisfied.

GECC must review recovery evidence and formally decide whether remaining risks are acceptable before production authorization.

### 8.5 Database and Backup Acceptance Testing

- Verify production, staging, and development database isolation.
- Confirm database accounts enforce approved least-privilege permissions.
- Verify PostgreSQL is inaccessible directly from the public internet.
- Test transaction rollback and database integrity constraints.
- Confirm approved Master Sales Records remain protected from modification.
- Verify database backup jobs complete and failures generate alerts.
- Restore a database backup into an isolated recovery environment.

- Restore customer documents and verify their database references.
- Test recovery using archived transaction logs where implemented.
- Verify recovered financial records, approvals, and audit history.
- Measure actual data loss and recovery time during restoration tests.
- Compare measured results with the approved zero-data-loss RPO and 15-minute RTO.
- Record test evidence, responsible personnel, and outstanding deficiencies.
- Require explicit GECC approval of unresolved recovery risks before launch.

Database and backup acceptance requires successful restoration evidence, not backup completion reports alone.

## 9. Production Application Deployment and Service Management

### 9.1 Production Application Deployment Architecture

- Production deployment must use an approved, version-controlled release.
- The Django backend must run through an approved production application server.
- The frontend must use a production build rather than a development server.
- Nginx or an approved equivalent must provide HTTPS reverse-proxy services.
- Production services must run under dedicated least-privilege accounts.
- Production settings and secrets must remain separate from development settings.
- Application and service dependencies must use tested, approved versions.

### 9.2 Application Service Management

- Production application services must be managed by an approved service supervisor.
- Required services must start automatically after an authorized server restart.
- Unexpected service failures must trigger controlled restart attempts.
- Repeated service failures must generate an operational alert.
- Application health checks must distinguish service availability from database connectivity.
- Service dependencies and startup order must be documented.
- Production services must support controlled startup, shutdown, and restart procedures.

- Service accounts must have only the permissions required for their functions.
- Application logs must be retained securely and protected from unauthorized modification.
- Logs must not expose passwords, authentication tokens, or other production secrets.
- Planned maintenance must use documented procedures and authorized personnel.
- Service configuration changes must be recorded and subject to change control.
- Restart testing must verify application access, database connectivity, and background services.
- Failed restart or maintenance procedures must trigger escalation and documented recovery actions.

Service-management acceptance requires demonstrated recovery from controlled restarts and representative service failures.

### 9.3 Production Release and Deployment Procedures

- Every production release must originate from an approved version-controlled commit.
- Each release must have a unique identifier and documented change summary.
- Automated tests and applicable security checks must pass before release approval.
- The release must be validated in an isolated staging environment.
- Database migrations must be reviewed for compatibility and recovery implications.
- Production deployment must require explicit authorization from an approved GECC authority.
- Deployment procedures must identify the operator, release version, and execution time.

- Each deployment must include pre-deployment health and backup verification.
- Production configuration and required secrets must be validated securely.
- Post-deployment checks must verify application access and critical workflows.
- Deployment failures must trigger a documented incident and recovery procedure.
- A tested application rollback procedure must be available before deployment.
- Database migration rollback limitations must be identified before approval.
- Release records must capture deployment results, approvals, and corrective actions.

Release acceptance requires successful verification of the deployed version and documented resolution of any blocking failures.

### 9.4 Production Configuration and Secrets Management

- Production configuration must be maintained separately from development and staging.
- VERIDIAN_ENVIRONMENT must explicitly identify the active deployment environment.
- Production must enforce DEBUG=False and prohibit development-only settings.
- Django secret keys, database credentials, and integration credentials must never be committed to source control.
- Production secrets must be stored using an approved protected mechanism.
- Access to production secrets must be restricted to authorized personnel and services.
- Secrets must not appear in application logs, diagnostic output, or deployment records.

- Production credentials must have documented issuance, rotation, and revocation procedures.
- Compromised or exposed credentials must be revoked and replaced promptly.
- Secret rotation must account for application availability and dependent services.
- Recovery procedures must provide authorized access to required secrets after a server failure.
- Recovery copies of secrets must be encrypted and protected separately from production systems.
- Production startup must reject missing or invalid security-critical configuration.
- Configuration changes must be tested, approved, dated, and auditable.

Configuration and secrets-management acceptance requires successful validation of production settings, credential recovery, and controlled rotation procedures.

### 9.5 Production Deployment Acceptance Testing

- Verify that the deployed application matches the approved release identifier.
- Confirm production uses DEBUG=False and the approved environment configuration.
- Verify HTTPS access and rejection of unauthorized administrative access.
- Test automatic service startup following an authorized server restart.
- Confirm application health checks and database connectivity.
- Verify that required background services operate correctly.
- Test authorized user login, role permissions, and project access restrictions.

- Test customer and project creation, approval, and stage transitions.
- Verify contract, invoice, and completion-certificate document workflows.
- Confirm financial records, payment tracking, and audit history remain accurate.
- Test authorized deployment rollback and recovery from a failed release.
- Verify monitoring alerts for representative application and service failures.
- Record test results, release identifiers, responsible personnel, and deficiencies.
- Require resolution of blocking deficiencies before production authorization.

Production deployment acceptance requires documented test evidence and explicit GECC authorization. Successful deployment alone does not constitute approval to begin production operations.

## 10. Production Monitoring, Operations, and Incident Response

### 10.1 Production Monitoring Architecture

- Production monitoring must cover server availability, application health, and database connectivity.
- Monitoring must track CPU, memory, storage utilization, and storage health.
- Monitoring must detect application service failures and repeated restart attempts.
- Database monitoring must identify connection failures, storage risks, and backup failures.
- HTTPS availability and certificate expiration must be monitored.
- Monitoring must detect failures affecting authorized remote user access.
- Monitoring records must be protected against unauthorized modification.

### 10.2 Monitoring Alerts and Notifications

- Monitoring alerts must be classified by operational severity.
- Critical alerts must identify failures affecting production availability, data integrity, or security.
- Alert notifications must identify the affected service and the time of detection.
- Each alert category must have an assigned response owner and escalation procedure.
- Critical alerts must reach authorized personnel through an approved notification channel.
- Alert delivery must not depend exclusively on the production server remaining operational.
- Alert acknowledgement, response actions, and resolution must be recorded.

### 10.3 Production Incident Response and Escalation

- Production incidents must be classified by severity and operational impact.
- Critical incidents must be escalated to designated GECC personnel.
- Each incident must have an assigned coordinator and authorized responders.

- Suspected security incidents must trigger containment and evidence preservation.
- Suspected data corruption must be investigated before records are modified or restored.
- Service restoration must follow documented and authorized recovery procedures.

- Incident records must document detection, response, recovery time, and business impact.
- Significant incidents must receive a documented post-incident review.
- Corrective actions must have assigned owners and tracked completion dates.

Incident closure requires documented recovery evidence and review of unresolved operational risks.

### 10.4 Routine Production Operations and Maintenance

- Designated personnel must review production health during scheduled operating hours.
- Routine checks must cover application availability and database connectivity.
- Backup completion and backup failure alerts must be reviewed regularly.
- Server storage capacity, disk health, and resource utilization must be monitored.
- Operating system and application security updates must follow an approved maintenance process.

- UPS battery condition and power-transfer operation must be tested periodically.
- Generator readiness and server power continuity must be verified.
- Network equipment and remote-access connectivity must receive scheduled checks.
- Maintenance activities must identify the responsible person and completion date.
- Planned service interruptions must be authorized and communicated in advance.

- Operational checklists must document completed checks and unresolved problems.
- Recurring maintenance findings must be reviewed and assigned corrective actions.
- Maintenance procedures must be reviewed after significant incidents or infrastructure changes.

Routine operations acceptance requires documented maintenance procedures, assigned responsibilities, and evidence that critical infrastructure checks can be completed successfully.

### 10.5 Production Monitoring and Operations Acceptance Testing

- Verify monitoring detects application and database service failures.
- Confirm server resource and storage-health alerts function correctly.
- Test notification delivery when the production server is unavailable.
- Verify critical alerts reach designated GECC responders.
- Test alert acknowledgement, escalation, and incident recording.

- Conduct a simulated critical incident and verify response procedures.
- Test UPS operation and server continuity during a simulated power interruption.
- Verify generator transfer and sustained power support under controlled conditions.
- Confirm routine maintenance checklists can be completed and recorded.
- Document test results, responsible personnel, and unresolved deficiencies.

- Blocking monitoring or operational deficiencies must be corrected before production authorization.
- Any unresolved availability or recovery risks must be disclosed to GECC leadership.

Production operations acceptance requires documented test evidence, assigned operational responsibilities, and explicit GECC authorization. Monitoring configuration alone does not establish operational readiness.

## 11. Production Infrastructure, Hardware, and Physical Security

### 11.1 Production Server Hardware Requirements

- Server hardware must be selected against documented application and database capacity requirements.
- The selected platform must support the approved production operating system.
- Production storage must provide redundancy appropriate to the approved risk tolerance.
- Memory capacity and reliability must support expected workloads and recovery operations.
- Hardware warranty, replacement availability, and support costs must be evaluated.

- Redundant internal power supplies must be preferred unless GECC explicitly approves an exception.
- Mirrored storage must not be treated as a substitute for independent backups.
- Hardware failure recovery must account for replacement parts and repair time.
- Server selection must include total acquisition and ongoing operating costs.
- Hardware limitations affecting the approved RPO or RTO must be documented.

- Candidate servers must be compared against a documented hardware requirements checklist.
- The final hardware selection must receive explicit GECC approval before purchase.
- Hardware acceptance must include storage, memory, power, and operating-system validation.

Hardware acceptance requires documented test evidence, cost approval, and disclosure of unresolved availability or recovery limitations.

### 11.2 Physical Security and Environmental Protection

- The production server must be located in a physically secure area.
- Physical access must be restricted to authorized personnel.
- Server placement must provide adequate ventilation and cooling.
- The installation area must be protected against water exposure and accidental damage.
- Physical access and significant equipment maintenance must be documented.

- Server temperature and cooling conditions must be monitored.
- Environmental risks must be assessed before selecting the server location.
- Server and network equipment must be protected against accidental disconnection.
- Independent backup equipment must receive appropriate physical protection.
- Equipment theft or unauthorized removal must trigger an incident response.

- The proposed server location must undergo a documented physical security inspection.
- Environmental protection and access restrictions must be verified before installation.
- Identified physical security deficiencies must be corrected or formally accepted by GECC.

Physical security acceptance requires documented inspection results, assigned responsibilities, and explicit approval of unresolved risks before production authorization.

### 11.3 Production Power Infrastructure and Continuity

- Production equipment must be connected to an appropriately sized UPS.
- UPS capacity must support server and essential network equipment during generator startup.
- The existing 17 kW natural-gas generator must be evaluated for production power support.
- Generator transfer time and UPS runtime must be measured under representative load.
- Power protection must account for the server, network, and independent backup equipment.

- UPS monitoring must detect battery faults and declining available runtime.
- Extended power failures must trigger a controlled server shutdown procedure.
- Generator failure must generate an operational alert through an independent channel.
- Power restoration procedures must verify equipment and database integrity.
- Electrical protection and maintenance must follow applicable safety requirements.

- Test UPS operation during a simulated utility power interruption.
- Verify generator transfer time against measured UPS runtime.
- Test controlled shutdown when generator power is unavailable.
- Verify recovery procedures after power restoration.
- Record test results, equipment limitations, and corrective actions.

Power continuity acceptance requires documented testing and GECC approval. The 15-minute recovery objective remains subject to end-to-end validation and explicit acceptance of any unmet requirements.

### 11.4 Network and Independent Backup Equipment

- Production network equipment must be identified and documented.
- The production firewall and router must support secure remote access.
- Essential network equipment must receive appropriate UPS protection.
- Network configuration backups must be maintained securely.
- Production network equipment must be protected from unauthorized physical access.

- Independent backup hardware must be separate from the production server.
- Backup storage must not depend on the production server remaining operational.
- Backup equipment must have restricted administrative access.
- Backup copies must be protected against unauthorized deletion and modification.
- Backup capacity and retention must be sized against documented recovery requirements.

- Verify backup equipment connectivity and authorized administrative access.
- Test backup creation, integrity verification, and restoration.
- Test recovery when the production server is unavailable.
- Confirm backup equipment monitoring and failure notifications.
- Document backup hardware, capacity, retention, and recovery test results.

Network and backup equipment acceptance requires documented testing, correction of critical deficiencies, and GECC approval before production authorization.

### 11.5 Infrastructure Acceptance Testing

- Verify the installed server hardware against the approved specifications.
- Verify storage redundancy, hardware health monitoring, and failure alerts.
- Confirm production network security and authorized remote connectivity.
- Verify UPS operation, generator transfer, and controlled shutdown.
- Confirm physical security, cooling, and environmental protections.

- Demonstrate restoration from independent backup equipment.
- Test representative server, storage, network, and power failure scenarios.
- Measure actual recovery time and potential data loss during recovery tests.
- Document test evidence, unresolved deficiencies, and corrective actions.
- Require GECC approval of the infrastructure acceptance record.

Infrastructure acceptance does not establish production readiness by itself. Any inability to meet the approved zero-data-loss objective or 15-minute recovery objective must be disclosed and resolved or explicitly addressed through a documented risk decision before production authorization.

## 12. Staging, End-to-End Validation, and Launch Gates

### 12.1 Staging Environment Requirements

- Staging must remain logically isolated from production.
- Staging must use production-equivalent application and database configurations where practical.
- Staging must not use live production credentials or unrestricted customer data.
- Application releases must be validated in staging before production deployment.
- Staging testing must include authorized user roles and representative project workflows.

### 12.2 End-to-End Business Workflow Validation

- Verify that a project reaches Completed Customer Record only when all required customer and project information is present.
- Verify that Contracted for Work requires a signed contract.
- Verify that Invoice Signed requires a signed invoice.
- Verify that Installation Scheduled requires a recorded installation schedule.
- Verify that Installation Complete requires a signed completion certificate.
- Verify that Payment Received reflects actual funds received by GECC.


- Verify that a project reaches Completed Customer Record only when all required customer and project information is present.
- Verify that Contracted for Work requires a signed contract.
- Verify that Invoice Signed requires a signed invoice.
- Verify that Installation Scheduled requires a recorded installation schedule.
- Verify that Installation Complete requires a signed completion certificate.
- Verify that Payment Received reflects actual funds received by GECC.

- Verify that deposits and full payments are reported separately under Payment Received.
- Verify that payment reporting does not remove a project from its applicable installation stage.
- Verify that selecting a dashboard stage displays the projects in that stage.
- Verify that all authorized users can access the project dashboard from Customers & Projects.
- Verify that Sales Managers, Installation Managers, and the Comptroller can view all projects.
- Verify that Sales Associates and Technical Associates can view only their assigned projects.

- Verify that Master Sales Records remain editable in Draft status and become immutable after approval.
- Verify that subsequent commercial changes create a new record version.
- Verify that temporary-duty authorizations specify permitted duties and effective dates.
- Verify that the Comptroller approves CEO temporary-duty assignments and the CEO approves Comptroller assignments.
- Verify that self-approval of temporary-duty assignments is prohibited.
- Verify that temporary-duty authorization, project access scope, and financial allocation remain separate controls.

- Verify that significant record changes and approval decisions produce attributable, timestamped audit entries.
- Verify that only the Comptroller can propose changes to controlled configuration values.
- Verify that configuration changes require approval and preserve version and effective-date history.
- Verify that contracts, invoices, and completion certificates follow their required signing workflows.
- Verify that GECC signature fields are included wherever required.
- Verify that the five-calendar-day installation waiting period is enforced where applicable.

- Verify that payroll reports include employees and contractors according to approved compensation rules.
- Verify that company financial reports include applicable employee and contractor transactions.
- Verify that financial report access follows approved role-based permissions.
- Test successful workflows and prohibited actions using representative user accounts.
- Record test results, supporting evidence, defects, and corrective actions.

End-to-end workflow acceptance requires documented successful testing of approved business rules, resolution of critical defects, and formal GECC approval.

### 12.3 Production Launch Readiness Gates

- Gate 1: Production hardware, network, power, and backup infrastructure must pass documented acceptance testing.
- Gate 2: Production identity, authentication, and role-based authorization must pass security validation.
- Gate 3: Database integrity, backup restoration, and disaster recovery procedures must be tested.
- Gate 4: Approved business workflows, document signing, payroll, and financial reporting must pass end-to-end validation.
- Gate 5: Production monitoring, alerting, incident response, and operational procedures must be verified.

- Gate 6: Production configuration, secrets, deployment procedures, and rollback arrangements must be approved.
- Gate 7: Recovery testing must establish actual data-loss and recovery-time performance against approved objectives.
- Gate 8: Critical defects and unresolved security vulnerabilities must be corrected before launch.
- Gate 9: Remaining operational risks must be documented, assigned, and formally reviewed by GECC.
- Gate 10: GECC must issue an explicit production go/no-go decision based on recorded acceptance evidence.

The approved objectives are zero data loss and recovery within 15 minutes. A single-server architecture may not achieve these objectives under every failure scenario. Any shortfall requires an explicit GECC risk decision; risk acceptance does not constitute technical compliance with an unmet objective.

## 13. Implementation Phases, Cost Decisions, Ownership, and Go/No-Go

### 13.1 Implementation Phases and Dependencies

- Phase 1: Approve the local hosting architecture, requirements, and implementation budget.
- Phase 2: Select and procure production server, network, UPS, and independent backup equipment.
- Phase 3: Install and secure the local infrastructure and establish isolated environments.
- Phase 4: Implement production identity, database, application services, monitoring, and backups.
- Phase 5: Complete staging validation, security testing, recovery exercises, and operational readiness.
- Phase 6: Review acceptance evidence and obtain an explicit GECC production go/no-go decision.

### 13.2 Hardware Procurement and Cost Decisions

- Obtain comparable quotations for suitable new and refurbished server equipment.
- Evaluate total cost, warranty, support, reliability, and expected service life.
- Identify the cost and availability of redundant internal power supplies.
- Include UPS, network security, independent backup storage, and replacement parts in the budget.
- Document any proposed deviation from the approved technical requirements.
- Require explicit GECC budget approval before equipment purchases.

### 13.3 Implementation Ownership and Responsibilities

- GECC executive leadership must approve the implementation budget and production launch decision.
- A designated technical owner must coordinate infrastructure installation and application deployment.
- A designated security owner must oversee identity, access controls, and security validation.
- A designated operations owner must oversee monitoring, backups, maintenance, and incident response.
- Business process owners must validate workflows, documents, payroll, and financial reporting.
- All responsibilities, delegated authorities, and approval decisions must be documented.

### 13.4 Implementation Risks and Outstanding Decisions

- Select a production server that balances affordability, reliability, and approved technical requirements.
- Decide whether redundant internal power supplies can be provided within the approved budget.
- Select suitable UPS, network security, and independent backup equipment.
- Validate the existing generator and available internet connectivity for production operations.
- Complete the production identity provider selection and integration.
- Determine whether the proposed architecture can meet the zero-data-loss and 15-minute recovery objectives.

- Maintain a risk register identifying each unresolved decision, its owner, and its impact.
- Assign a target resolution date and required evidence to each outstanding item.
- Record cost, security, availability, and recovery implications of proposed decisions.
- Document approved technical deviations and their associated residual risks.
- Escalate risks that could prevent compliance with production launch requirements.

All material implementation risks must be reviewed before the final production go/no-go decision. Acceptance of a risk does not demonstrate that an unmet technical requirement has been satisfied.

### 13.5 Separation of Development, Staging, and Production Requirements

- Level 1: Local software development and UI implementation may continue without production hardware procurement or production infrastructure acceptance.
- Level 2: Staging, integration testing, and business workflow validation may continue without satisfying final production launch gates.
- Level 3: Production deployment requires completion of applicable launch gates and formal GECC authorization.
- Production infrastructure, resilience, and recovery objectives must not become prerequisites for unrelated Level 1 or Level 2 work.
- Appropriate authentication, authorization, data protection, and development security safeguards remain mandatory at every level.

GECC explicitly approves this separation. Unmet Level 3 requirements may block production authorization but must not independently block continued Level 1 development or Level 2 staging and validation.

### 13.6 Final Production Go/No-Go Decision

- The production decision must be based on documented evidence for all applicable launch gates.
- GECC must review unresolved defects, security findings, operational risks, and recovery limitations.
- Each material exception must identify its owner, consequences, corrective action, and approval status.
- The final decision must identify the authorized production environment and approved release version.
- Production deployment must not proceed without an explicit, dated GECC authorization.

Until formal production authorization is granted, VERIDIAN remains eligible for continued development and staging validation but is not approved for live production operations.
