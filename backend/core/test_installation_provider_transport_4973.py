"""Transport tests exercise the real path validator with a mocked opener.

No network request and no database writes.
"""
import json
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError

from .installation_provider_readback_4972 import _reader

M = "core.installation_provider_readback_4972"
ACCOUNT = "11111111-1111-4111-8111-111111111111"
ENVELOPE = "22222222-2222-4222-8222-222222222222"
BASE = (
    f"/restapi/v2.1/accounts/{ACCOUNT}"
    f"/envelopes/{ENVELOPE}"
)
TOKEN = "synthetic-test-token-not-real"


class Response:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return BytesIO(self.content)

    def __exit__(self, *args):
        return False


def opener(content):
    class FakeOpener:
        def open(self, request, timeout):
            if request.get_method() != "GET":
                raise AssertionError("Unexpected HTTP method.")
            if not request.full_url.startswith(
                "https://demo.docusign.net/restapi/v2.1/"
            ):
                raise AssertionError("Unexpected provider host.")
            return Response(content)
    return FakeOpener()


class InspectionTransportBoundary4973Tests(TestCase):
    def test_all_three_json_endpoints(self):
        content = json.dumps({"status": "completed"}).encode()
        with patch(M + ".build_opener", return_value=opener(content)) as network:
            for suffix in ("", "/recipients", "/recipients/1/tabs"):
                result = _reader(BASE + suffix, TOKEN)
                self.assertEqual(result["status"], "completed")
            self.assertEqual(network.call_count, 3)

    def test_both_pdf_endpoints(self):
        content = b"%PDF-1.4\nsynthetic"
        with (
            patch(M + ".build_opener", return_value=opener(content)),
            patch(M + ".PdfReader") as pdf_reader,
        ):
            pdf_reader.return_value.is_encrypted = False
            pdf_reader.return_value.pages = [object()]
            self.assertEqual(
                _reader(BASE + "/documents/1", TOKEN, pdf=True),
                content,
            )
            self.assertEqual(
                _reader(
                    BASE + "/documents/certificate",
                    TOKEN,
                    pdf=True,
                ),
                content,
            )

    def test_extra_paths_and_queries_denied_without_network(self):
        invalid = [
            BASE + "/audit_events/extra",
            BASE + "/recipients/2/tabs",
            BASE + "/recipients/1/tabs/extra",
            BASE + "/documents/2",
            BASE + "/documents/1?x=1",
            BASE + "?include=all",
            BASE + "/documents/certificate/extra",
            "/restapi/v2.1/accounts/" + ACCOUNT,
            "https://example.com" + BASE,
            BASE.replace("/envelopes/", "/envelopes//"),
        ]
        with patch(M + ".build_opener") as network:
            for path in invalid:
                with self.subTest(path=path):
                    with self.assertRaises(ValidationError):
                        _reader(path, TOKEN)
            network.assert_not_called()

    def test_noncanonical_ids_denied(self):
        invalid = [
            BASE.replace(ACCOUNT, "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"),
            BASE.replace(ENVELOPE, "not-an-envelope-id"),
            BASE.replace(ACCOUNT, "00000000-0000-0000-0000-00000000000z"),
        ]
        with patch(M + ".build_opener") as network:
            for path in invalid:
                with self.assertRaises(ValidationError):
                    _reader(path, TOKEN)
            network.assert_not_called()

    def test_pdf_json_type_confusion_denied(self):
        with patch(M + ".build_opener") as network:
            with self.assertRaises(ValidationError):
                _reader(BASE + "/documents/1", TOKEN)
            with self.assertRaises(ValidationError):
                _reader(BASE + "/recipients", TOKEN, pdf=True)
            network.assert_not_called()

    def test_failed_network_is_closed_without_token_disclosure(self):
        with patch(
            M + ".build_opener",
            side_effect=RuntimeError("synthetic network failure"),
        ):
            with self.assertRaises(ValidationError) as error:
                _reader(BASE, TOKEN)
        self.assertNotIn(TOKEN, str(error.exception))

    def test_oversize_json_rejected(self):
        with patch(
            M + ".build_opener",
            return_value=opener(b"X" * 262145),
        ):
            with self.assertRaises(ValidationError):
                _reader(BASE, TOKEN)
