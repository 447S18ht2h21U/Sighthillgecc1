"""TEST-ONLY receipt routing. Never import into operational URLs."""
from django.urls import path

from .receipt_outbox_api_prototype_4208 import (
    ReceiptOutboxRequestPrototype,
)
from .receipt_outbox_status_api_prototype_4209 import (
    ReceiptOutboxStatusPrototype,
)

urlpatterns = [
    path(
        "test-only/receipt-outbox/",
        ReceiptOutboxRequestPrototype.as_view(),
        name="test-only-receipt-request",
    ),
    path(
        "test-only/receipt-outbox/<uuid:outbox_id>/",
        ReceiptOutboxStatusPrototype.as_view(),
        name="test-only-receipt-status",
    ),
]