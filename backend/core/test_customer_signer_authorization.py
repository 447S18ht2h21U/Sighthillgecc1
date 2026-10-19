"""Isolated integration tests for customer-signer approval and audit integrity."""

from unittest.mock import patch

from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import tests as foundation
from .customer_signer_authorization_services import approve_customer_signer, revoke_customer_signer
from .models import AuditEvent, CustomerSignerAuthorization, CustomerSignerRevocation


@override_settings(DEBUG=True)
class CustomerSignerAuthorizationTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def authorization_arguments(self):
        self.approve()

        self.project.refresh_from_db()

        return {
            "project": self.project,
            "customer": self.project.customer,
            "group": "COMMERCIAL",
            "signer_name": "Synthetic Authorized Customer",
            "signer_email": "synthetic@example.com",
            "authority_basis": "Synthetic documented authorization",
            "evidence_reference": "SYNTHETIC-EVIDENCE-001",
            "requested_by": self.sales,
            "approved_by": self.manager,
        }

    def test_approval_creates_immutable_record_and_audit_event(self):
        arguments = self.authorization_arguments()
        before = AuditEvent.objects.count()

        authorization = approve_customer_signer(**arguments)

        self.assertTrue(
            CustomerSignerAuthorization.objects.filter(
                pk=authorization.pk
            ).exists()
        )
        self.assertEqual(len(authorization.digest), 64)
        self.assertEqual(AuditEvent.objects.count(), before + 1)
        self.assertTrue(
            AuditEvent.objects.filter(
                entity_id=authorization.pk,
                action="CUSTOMER_SIGNER_AUTHORIZATION_APPROVED",
            ).exists()
        )

    def test_audit_failure_rolls_back_authorization(self):
        arguments = self.authorization_arguments()
        before_authorizations = CustomerSignerAuthorization.objects.count()
        before_audit_events = AuditEvent.objects.count()

        with patch(
            "core.services.audit",
            side_effect=RuntimeError("Synthetic audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                approve_customer_signer(**arguments)

        self.assertEqual(
            CustomerSignerAuthorization.objects.count(),
            before_authorizations,
        )
        self.assertEqual(AuditEvent.objects.count(), before_audit_events)

    def test_requester_cannot_approve_own_authorization(self):
        arguments = self.authorization_arguments()
        arguments["requested_by"] = self.manager

        with self.assertRaises(PermissionDenied):
            approve_customer_signer(**arguments)

        self.assertFalse(CustomerSignerAuthorization.objects.exists())

    def test_database_rejects_authorization_update_and_delete(self):
        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CustomerSignerAuthorization.objects.filter(
                    pk=authorization.pk
                ).update(signer_name="Unauthorized Change")

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CustomerSignerAuthorization.objects.filter(
                    pk=authorization.pk
                ).delete()

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.signer_name,
            "Synthetic Authorized Customer",
        )

    def test_nonapproved_msr_rejected(self):
        arguments = self.authorization_arguments()
        from .customer_signer_authorization_services import validate_signer_evidence

        self.project.current_approved.status = "SUBMITTED"

        with self.assertRaises(ValidationError):
            validate_signer_evidence(
                project=self.project,
                customer=arguments["customer"],
                group=arguments["group"],
                signer_name=arguments["signer_name"],
                signer_email=arguments["signer_email"],
                authority_basis=arguments["authority_basis"],
                evidence_reference=arguments["evidence_reference"],
            )

        self.assertFalse(
            CustomerSignerAuthorization.objects.exists()
        )

    def test_revocation_preserves_authorization_and_creates_audit_event(self):
        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)
        original_digest = authorization.digest
        original_approved_at = authorization.approved_at
        before = AuditEvent.objects.count()

        revocation = revoke_customer_signer(
            authorization_id=authorization.pk,
            revoked_by=self.manager,
            reason="Synthetic customer authority withdrawn",
        )

        authorization.refresh_from_db()
        self.assertEqual(authorization.digest, original_digest)
        self.assertEqual(authorization.approved_at, original_approved_at)
        self.assertEqual(revocation.authorization_id, authorization.pk)
        self.assertEqual(
            revocation.reason,
            "Synthetic customer authority withdrawn",
        )
        self.assertEqual(len(revocation.digest), 64)
        self.assertEqual(CustomerSignerRevocation.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), before + 1)
        self.assertTrue(
            AuditEvent.objects.filter(
                entity_id=revocation.pk,
                action="CUSTOMER_SIGNER_AUTHORIZATION_REVOKED",
            ).exists()
        )

    def test_duplicate_revocation_rejected(self):
        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)

        first = revoke_customer_signer(
            authorization_id=authorization.pk,
            revoked_by=self.manager,
            reason="Synthetic initial revocation",
        )

        before_audit_events = AuditEvent.objects.count()

        with self.assertRaises(ValidationError):
            revoke_customer_signer(
                authorization_id=authorization.pk,
                revoked_by=self.manager,
                reason="Synthetic duplicate revocation attempt",
            )

        self.assertEqual(CustomerSignerRevocation.objects.count(), 1)
        self.assertTrue(
            CustomerSignerRevocation.objects.filter(
                pk=first.pk,
                reason="Synthetic initial revocation",
            ).exists()
        )
        self.assertEqual(
            AuditEvent.objects.count(),
            before_audit_events,
        )
    def test_revocation_audit_failure_rolls_back(self):
        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)
        before_audit_events = AuditEvent.objects.count()

        with patch(
            "core.services.audit",
            side_effect=RuntimeError("Synthetic revocation audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                revoke_customer_signer(
                    authorization_id=authorization.pk,
                    revoked_by=self.manager,
                    reason="Synthetic rollback verification",
                )

        self.assertFalse(
            CustomerSignerRevocation.objects.filter(
                authorization_id=authorization.pk
            ).exists()
        )
        self.assertEqual(
            AuditEvent.objects.count(),
            before_audit_events,
        )
        self.assertTrue(
            CustomerSignerAuthorization.objects.filter(
                pk=authorization.pk
            ).exists()
        )
    def test_database_rejects_revocation_update_and_delete(self):
        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)
        revocation = revoke_customer_signer(
            authorization_id=authorization.pk,
            revoked_by=self.manager,
            reason="Synthetic permanent revocation",
        )

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CustomerSignerRevocation.objects.filter(
                    pk=revocation.pk
                ).update(reason="Unauthorized modification")

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CustomerSignerRevocation.objects.filter(
                    pk=revocation.pk
                ).delete()

        revocation.refresh_from_db()
        self.assertEqual(
            revocation.reason,
            "Synthetic permanent revocation",
        )
        self.assertTrue(
            CustomerSignerAuthorization.objects.filter(
                pk=authorization.pk
            ).exists()
        )
    def test_sales_associate_cannot_revoke_customer_signer(self):
        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)
        before_audit_events = AuditEvent.objects.count()

        with self.assertRaises(PermissionDenied):
            revoke_customer_signer(
                authorization_id=authorization.pk,
                revoked_by=self.sales,
                reason="Synthetic unauthorized revocation attempt",
            )

        self.assertFalse(
            CustomerSignerRevocation.objects.filter(
                authorization_id=authorization.pk
            ).exists()
        )
        self.assertEqual(
            AuditEvent.objects.count(),
            before_audit_events,
        )
        self.assertTrue(
            CustomerSignerAuthorization.objects.filter(
                pk=authorization.pk
            ).exists()
        )
    def test_sales_manager_cannot_revoke_completion_authorization(self):
        arguments = self.authorization_arguments()
        arguments["group"] = (
            "COMPLETION_" +
            self.project.current_approved.snapshot["financing_type"]
        )
        arguments["approved_by"] = self.manager
        arguments["requested_by"] = self.sales

        from .customer_signer_authorization_services import require_authorized_revoker
        from .models import Role

        authorization = CustomerSignerAuthorization(
            project=self.project,
            customer=self.project.customer,
            group=arguments["group"],
            signer_name=arguments["signer_name"],
            signer_email=arguments["signer_email"],
            authority_basis=arguments["authority_basis"],
            evidence_reference=arguments["evidence_reference"],
            requested_by=self.sales,
            approved_by=self.manager,
        )

        self.assertEqual(self.manager.role, Role.SALES_MANAGER)
        with self.assertRaises(PermissionDenied):
            require_authorized_revoker(
                revoked_by=self.manager,
                authorization=authorization,
            )
    def test_installation_manager_cannot_revoke_commercial_authorization(self):
        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)

        from .customer_signer_authorization_services import require_authorized_revoker
        from .models import Role, User

        installation_manager = User.objects.create_user(
            username="synthetic_installation_revoker",
            password="SyntheticTestPassword123!",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )

        before_audit_events = AuditEvent.objects.count()

        with self.assertRaises(PermissionDenied):
            require_authorized_revoker(
                revoked_by=installation_manager,
                authorization=authorization,
            )

        self.assertFalse(
            CustomerSignerRevocation.objects.filter(
                authorization_id=authorization.pk
            ).exists()
        )
        self.assertEqual(
            AuditEvent.objects.count(),
            before_audit_events,
        )
    def test_installation_manager_can_revoke_completion_authorization(self):
        from .models import Role, User
        from django.utils import timezone

        arguments = self.authorization_arguments()
        installation_manager = User.objects.create_user(
            username="synthetic_completion_revoker",
            password="SyntheticTestPassword123!",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )
        group = (
            "COMPLETION_" +
            self.project.current_approved.snapshot["financing_type"]
        )
        authorization = CustomerSignerAuthorization.objects.create(
            project=self.project,
            customer=self.project.customer,
            group=group,
            signer_name=arguments["signer_name"],
            signer_email=arguments["signer_email"],
            authority_basis=arguments["authority_basis"],
            evidence_reference=arguments["evidence_reference"],
            requested_by=self.sales,
            approved_by=installation_manager,
            approved_at=timezone.now(),
            digest="a" * 64,
        )
        before_audit_events = AuditEvent.objects.count()

        revocation = revoke_customer_signer(
            authorization_id=authorization.pk,
            revoked_by=installation_manager,
            reason="Synthetic completion authority withdrawn",
        )

        self.assertEqual(revocation.authorization_id, authorization.pk)
        self.assertEqual(revocation.revoked_by_id, installation_manager.pk)
        self.assertEqual(CustomerSignerRevocation.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), before_audit_events + 1)
        self.assertTrue(AuditEvent.objects.filter(
            entity_id=revocation.pk,
            action="CUSTOMER_SIGNER_AUTHORIZATION_REVOKED",
        ).exists())
        self.assertTrue(
            CustomerSignerAuthorization.objects.filter(
                pk=authorization.pk
            ).exists()
        )
    def test_comptroller_can_revoke_commercial_authorization(self):
        from .models import Role, User

        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)

        comptroller = User.objects.create_user(
            username="synthetic_comptroller_revoker",
            password="SyntheticTestPassword123!",
            role=Role.COMPTROLLER,
            initials="CO",
        )

        before_audit_events = AuditEvent.objects.count()

        revocation = revoke_customer_signer(
            authorization_id=authorization.pk,
            revoked_by=comptroller,
            reason="Synthetic Comptroller commercial revocation",
        )

        self.assertEqual(revocation.authorization_id, authorization.pk)
        self.assertEqual(revocation.revoked_by_id, comptroller.pk)
        self.assertEqual(CustomerSignerRevocation.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), before_audit_events + 1)
        self.assertTrue(
            AuditEvent.objects.filter(
                entity_id=revocation.pk,
                action="CUSTOMER_SIGNER_AUTHORIZATION_REVOKED",
            ).exists()
        )
        self.assertTrue(
            CustomerSignerAuthorization.objects.filter(
                pk=authorization.pk
            ).exists()
        )
    def test_comptroller_can_revoke_completion_authorizations(self):
        from .models import Role, User
        from django.utils import timezone

        arguments = self.authorization_arguments()
        comptroller = User.objects.create_user(
            username="synthetic_completion_comptroller",
            password="SyntheticTestPassword123!",
            role=Role.COMPTROLLER,
            initials="CO",
        )

        for group in ("COMPLETION_FINANCED", "COMPLETION_NON_FINANCED"):
            with self.subTest(group=group):
                authorization = CustomerSignerAuthorization.objects.create(
                    project=self.project,
                    customer=self.project.customer,
                    group=group,
                    signer_name=arguments["signer_name"],
                    signer_email=arguments["signer_email"],
                    authority_basis=arguments["authority_basis"],
                    evidence_reference=arguments["evidence_reference"],
                    requested_by=self.sales,
                    approved_by=comptroller,
                    approved_at=timezone.now(),
                    digest="b" * 64,
                )
                before_audit_events = AuditEvent.objects.count()

                revocation = revoke_customer_signer(
                    authorization_id=authorization.pk,
                    revoked_by=comptroller,
                    reason="Synthetic Comptroller completion revocation",
                )

                self.assertEqual(revocation.authorization_id, authorization.pk)
                self.assertEqual(revocation.revoked_by_id, comptroller.pk)
                self.assertEqual(AuditEvent.objects.count(), before_audit_events + 1)
                self.assertTrue(AuditEvent.objects.filter(
                    entity_id=revocation.pk,
                    action="CUSTOMER_SIGNER_AUTHORIZATION_REVOKED",
                ).exists())
                self.assertTrue(CustomerSignerAuthorization.objects.filter(
                    pk=authorization.pk
                ).exists())
    def test_blank_revocation_reason_rejected(self):
        arguments = self.authorization_arguments()
        authorization = approve_customer_signer(**arguments)
        before = AuditEvent.objects.count()

        for reason in ("", "   ", None):
            with self.subTest(reason=reason):
                with self.assertRaises(ValidationError):
                    revoke_customer_signer(
                        authorization_id=authorization.pk,
                        revoked_by=self.manager,
                        reason=reason,
                    )

        self.assertFalse(
            CustomerSignerRevocation.objects.filter(
                authorization_id=authorization.pk
            ).exists()
        )
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_invalid_signer_evidence_rejected(self):
        arguments = self.authorization_arguments()
        before = AuditEvent.objects.count()

        for field, invalid_value in (
            ("authority_basis", "   "),
            ("evidence_reference", ""),
            ("signer_email", "invalid-email"),
            ("signer_name", ""),
        ):
            with self.subTest(field=field):
                candidate = arguments.copy()
                candidate[field] = invalid_value
                with self.assertRaises(ValidationError):
                    approve_customer_signer(**candidate)

        self.assertFalse(CustomerSignerAuthorization.objects.exists())
        self.assertEqual(AuditEvent.objects.count(), before)
    def test_unassigned_sales_manager_cannot_revoke(self):
        from .models import Role, User

        authorization = approve_customer_signer(
            **self.authorization_arguments()
        )
        other_manager = User.objects.create_user(
            username="synthetic_unassigned_sales_manager",
            password="SyntheticTestPassword123!",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        before = AuditEvent.objects.count()

        with self.assertRaises(PermissionDenied):
            revoke_customer_signer(
                authorization_id=authorization.pk,
                revoked_by=other_manager,
                reason="Synthetic unauthorized manager revocation",
            )

        self.assertFalse(
            CustomerSignerRevocation.objects.filter(
                authorization_id=authorization.pk
            ).exists()
        )
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_inactive_comptroller_cannot_revoke(self):
        from .models import Role, User

        authorization = approve_customer_signer(
            **self.authorization_arguments()
        )
        inactive_comptroller = User.objects.create_user(
            username="synthetic_inactive_comptroller",
            password="SyntheticTestPassword123!",
            role=Role.COMPTROLLER,
            initials="CO",
            is_active=False,
        )
        before = AuditEvent.objects.count()

        with self.assertRaises(PermissionDenied):
            revoke_customer_signer(
                authorization_id=authorization.pk,
                revoked_by=inactive_comptroller,
                reason="Synthetic inactive Comptroller revocation",
            )

        self.assertFalse(
            CustomerSignerRevocation.objects.filter(
                authorization_id=authorization.pk
            ).exists()
        )
        self.assertEqual(AuditEvent.objects.count(), before)