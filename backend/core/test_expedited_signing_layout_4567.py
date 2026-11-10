import ast
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.test import SimpleTestCase

from .expedited_signing_layout_4567 import (
    CANDIDATES, REFERENCES, candidate_layout,
)

REFERENCE_ROOT = (
    Path(settings.BASE_DIR).parent
    / "docs/reference/GECC-20261107-final-seven"
)


class ExpeditedSigningLayout4567Tests(SimpleTestCase):
    def test_exact_approved_references_and_candidates(self):
        result = candidate_layout(REFERENCE_ROOT)
        self.assertEqual(len(result["documents"]), 2)
        self.assertEqual(len(result["tabs"]), 4)
        self.assertFalse(result["visually_approved"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["customer_initials_verified"])
        self.assertFalse(result["installation_authorized"])

    def test_reference_fingerprints_agree_with_v2_mapping(self):
        path = Path(settings.BASE_DIR) / "core/v2_document_mapping_4489.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        mapping = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name)
                and target.id == "REFERENCE_FILES"
                for target in node.targets
            ):
                mapping = ast.literal_eval(node.value)
                break
        self.assertIsNotNone(mapping)
        for kind, (filename, fingerprint, _) in REFERENCES.items():
            self.assertEqual(mapping[kind], (filename, fingerprint))

    def test_original_document_files_never_changed(self):
        before = {
            kind: (REFERENCE_ROOT / entry[0]).read_bytes()
            for kind, entry in REFERENCES.items()
        }
        candidate_layout(REFERENCE_ROOT)
        for kind, entry in REFERENCES.items():
            self.assertEqual(
                (REFERENCE_ROOT / entry[0]).read_bytes(), before[kind]
            )

    def test_missing_reference_rejected(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                candidate_layout(directory)

    def test_tampered_reference_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, _, _ in REFERENCES.values():
                (root / filename).write_bytes(
                    (REFERENCE_ROOT / filename).read_bytes()
                )
            target = root / REFERENCES["EXPEDITED_SERVICE"][0]
            target.write_bytes(target.read_bytes() + b"changed")
            with self.assertRaises(ValueError):
                candidate_layout(root)

    def test_candidate_rectangles_use_expected_pages(self):
        result = candidate_layout(REFERENCE_ROOT)
        self.assertEqual(
            result["tabs"]["sow_customer_initials"]["pageNumber"], "1"
        )
        self.assertEqual(
            result["tabs"]["expedited_customer_signature"]["documentId"],
            "2",
        )
        self.assertEqual(
            result["tabs"]["sow_proposed_date"]["tabLabel"],
            "proposed-install-date",
        )

    def test_tab_names_are_unique(self):
        labels = [item["tabLabel"] for item in CANDIDATES.values()]
        self.assertEqual(len(labels), len(set(labels)))
