# VERIDIAN Local Hosting Architecture Decision — Version 1

## 1. Document Control

Status: Approved Hosting Direction — Technical Validation Pending
Project: VERIDIAN
Organization: GECC
Decision Date: October 12, 2026
Decision Authority: GECC

## 2. Approved Hosting Direction

GECC has approved deferring AWS production hosting because the company is operating with limited capital and wishes to avoid unnecessary recurring infrastructure expenses.

The preferred initial production hosting architecture is a GECC-owned server operating on the company's local network.

AWS remains a possible future hosting or disaster recovery option. No AWS deployment commitment is authorized by this decision.

## 3. Operational Requirements

- Required availability: 8:00 AM to 8:00 PM Eastern Time.
- Secure remote user access is required.
- Local backup capability is required.
- N+1 power supply redundancy is required.
- Recovery Point Objective (RPO): zero data loss.
- Recovery Time Objective (RTO): 15 minutes.
- Production, staging, and development environments must remain appropriately separated.

## 4. Technical Validation Pending

The following must be evaluated before production authorization:

- Server processor, memory, storage, and reliability.
- UPS capacity, runtime, and redundant power paths.
- Database durability and recovery mechanisms.
- Local backup architecture and restore procedures.
- Network reliability and secure remote access.
- Server failure recovery and continuity arrangements.
- Recovery testing against approved RPO and RTO requirements.

## 5. Authorization Boundary

Approval of local hosting does not constitute approval of a specific server, backup design, security configuration, or production launch.

Hardware selection, recovery design, testing, and production readiness approval remain outstanding.
