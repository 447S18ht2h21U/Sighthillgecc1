# VERIDIAN Environment Configuration Standard v1.0

## Document Control

| Field | Value |
|---|---|
| System | VERIDIAN Business Operations & Management System |
| Document | Environment Configuration Standard |
| Version | 1.0 |
| Status | Controlled Draft |
| Purpose | Define approved configuration requirements for each deployment environment |

---

# 1. Environment Model

VERIDIAN operates using three explicit environments:

| Environment | Purpose |
|---|---|
| Development | Local engineering, automated testing, synthetic data, sandbox validation |
| Staging | Production-like validation and controlled integration testing |
| Production | Live GECC business operations |

The deployment environment must always be explicitly identified.

---
# 2. Development Environment

Required configuration:

    VERIDIAN_ENVIRONMENT=development
    GECC_DEV=1
    DEBUG=True

Purpose:

Development supports local engineering, automated testing, synthetic data, and approved sandbox validation.

Allowed capabilities:

- Development authentication.
- Synthetic document templates.
- Sandbox DocuSign verification.
- Sandbox reconciliation.
- Sandbox package generation.
- Signing-test workflows.

Security rule:

Development-only capabilities must never be enabled solely because DEBUG is enabled.

A feature requiring development access must validate:

1. Explicit environment identity.
2. Development mode authorization.

---

# 3. Staging Environment

Required configuration:

    VERIDIAN_ENVIRONMENT=staging
    GECC_DEV=0
    DEBUG=False

Purpose:

Staging provides production-like validation and controlled integration testing.

Staging is used to verify application behavior before production release.

Restrictions:

- No development authentication.
- No development bootstrap tools.
- No synthetic document bypass.
- No sandbox-only operational workflows.
- No development-only signing tools.

Staging must preserve production security behavior while allowing approved validation activities.

---

# 4. Production Environment

Required configuration:

    VERIDIAN_ENVIRONMENT=production
    GECC_DEV=0
    DEBUG=False

Purpose:

Production supports live GECC business operations.

Production environments contain real business data, production credentials, and approved operational workflows.

Restrictions:

- No development authentication.
- No development bootstrap tools.
- No synthetic document generation.
- No sandbox workflows.
- No test signing operations.
- No development-only operational tools.

Production releases require completion of approved readiness gates and supporting evidence.

---

# 5. Security Rules

## Environment Authorization

A feature requiring development access must validate:

1. Explicit environment identity.
2. Development mode authorization.

DEBUG alone is not an authorization mechanism.

---

## Secret Management

Production secrets:

- Must not exist in source control.
- Must be stored using approved secret-management controls.
- Must use controlled access policies.

Local development secrets must remain separate from staging and production credentials.

---

## Deployment Validation

Before deployment, verify:

- Correct VERIDIAN_ENVIRONMENT value.
- DEBUG setting matches the target environment.
- Development flags are disabled outside development.
- Required secrets exist.
- Database configuration matches the environment.
- External integrations match the environment.

---

# 6. Database Configuration

Development:

- Local development databases are permitted.
- Synthetic development data may be used.

Staging and Production:

- PostgreSQL is required.
- Controlled database credentials are required.
- Production database access must follow approved security controls.

---

# 7. External Integrations

Development:

- Sandbox integrations are permitted.
- Sandbox credentials must not be used outside development.

Staging:

- Controlled integration testing is permitted after approval.
- Staging credentials and endpoints must remain separate from production.

Production:

- Production credentials only.
- Production endpoints only.
- Development and sandbox integrations are prohibited.

---

# 8. Change Control

Changes affecting environment behavior require:

- Documented rationale.
- Code review.
- Regression testing.
- Updated readiness evidence.

Environment configuration changes must maintain separation between:

- Development capabilities.
- Staging validation.
- Production business operations.

---

# Approval Status

This document defines the approved VERIDIAN environment configuration model.

The standard supports controlled movement from development through staging to production while preventing development-only capabilities from being enabled in non-development environments.

---
