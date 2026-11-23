import io
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from urllib.error import HTTPError

from .docusign import request_json


class DocusignOAuthErrorTests(SimpleTestCase):
    def check_error(self, response_body, expected):
        error = HTTPError(
            "https://account-d.docusign.com/oauth/token",
            400,
            "Bad Request",
            {},
            io.BytesIO(response_body),
        )
        with patch("core.docusign.build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(ValidationError) as caught:
                request_json(
                    "/oauth/token",
                    "Basic fictional-test-value",
                    {"grant_type": "authorization_code", "code": "test-only"},
                )

        message = str(caught.exception.detail)
        self.assertIn(expected, message)
        return message

    def test_invalid_client_category(self):
        message = self.check_error(
            b'{"error":"invalid_client","error_description":"PRIVATE"}',
            "invalid_client",
        )
        self.assertNotIn("PRIVATE", message)

    def test_invalid_grant_category(self):
        self.check_error(b'{"error":"invalid_grant"}', "invalid_grant")

    def test_unknown_response_is_not_disclosed(self):
        message = self.check_error(
            b'{"error":"sensitive_unexpected_value","token":"PRIVATE"}',
            "HTTP 400",
        )
        self.assertNotIn("PRIVATE", message)
        self.assertNotIn("sensitive_unexpected_value", message)
