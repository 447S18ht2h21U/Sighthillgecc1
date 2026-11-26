"""Local distributor invoice extraction.

All extracted information is unverified.

This module does not persist documents, change approved selling
prices, establish payment evidence or authorize business actions.
"""

import io
import os
import re
import shutil
import subprocess
import tempfile

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from hashlib import sha256


MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 25000000
MAX_TEXT_LENGTH = 100000
MAX_PDF_PAGES = 20


class InvoiceExtractionError(Exception):
    pass


def find_tesseract():

    candidates = [
        os.environ.get("VERIDIAN_TESSERACT_PATH"),
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]

    for candidate in candidates:

        if not candidate:
            continue

        path = Path(candidate)

        if path.is_file():
            return str(path.resolve())

    return None


def _unique(values):

    result = []

    for value in values:

        if value and value not in result:
            result.append(value)

    return result


def _suggest(values):

    candidates = _unique(values)

    return {
        "value": candidates[0] if len(candidates) == 1 else None,
        "candidates": candidates,
        "status": (
            "SUGGESTED"
            if len(candidates) == 1
            else "AMBIGUOUS"
            if candidates
            else "NOT_FOUND"
        ),
        "employee_confirmation_required": True,
    }


def _date_candidates(text):

    values = []

    # Recognize invoice date labels appearing in columns.
    # Do not substitute a due date or shipping date.

    matches = re.findall(
        r"(?im)(?:^|[ \t]{2,})"
        r"(?:invoice[ \t]+date|date)"
        r"[ \t]*[:#]?[ \t]*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|\d{4}-\d{2}-\d{2})\b",
        text,
    )

    for value in matches:

        for pattern in (
            "%m/%d/%Y",
            "%m/%d/%y",
            "%m-%d-%Y",
            "%m-%d-%y",
            "%Y-%m-%d",
        ):

            try:
                parsed = datetime.strptime(
                    value, pattern
                ).date()

            except ValueError:
                continue

            values.append(parsed.isoformat())
            break

    return values


def _total_candidates(text):

    result = []

    # Accept explicit invoice total labels and limited OCR
    # variations. Do not substitute balance due or subtotal.

    matches = re.findall(
        r"(?im)^[ \t|_-]*"
        r"(?:invoice[ \t]+total|"
        r"grand[ \t]+total|"
        r"(?:job|ob)[ \t]+total|"
        r"total)\b"
        r"[^\n$0-9]{0,40}"
        r"\$?[ \t]*"
        r"([0-9][0-9,]*\.\d{2})"
        r"[ \t|]*$",
        text,
    )

    for value in matches:

        try:
            amount = Decimal(
                value.replace(",", "")
            )

        except InvalidOperation:
            continue

        if (
            amount.is_finite()
            and Decimal("0.00") < amount
            <= Decimal("9999999999.99")
        ):

            result.append(
                format(amount, ".2f")
            )

    return result


def _equipment_candidates(text):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    explicit_model = re.compile(
        r"(?i)\b(?:model(?:\s+(?:number|no\.?))?|m/n)"
        r"\s*[:#]?\s+"
        r"([A-Z0-9][A-Z0-9._/-]{3,63})\b"
    )

    standalone_model = re.compile(
        r"(?i)^[| \t_-]*"
        r"([A-Z0-9][A-Z0-9._/-]{5,63})"
        r"(?:[ \t]{2,}.*)?$"
    )

    serial_pattern = re.compile(
        r"(?i)\b(?:serial(?:\s+(?:number|no\.?))?|s/n|sn)"
        r"\s*[:#]?\s*"
        r"([A-Z0-9][A-Z0-9._/-]{3,63})\b"
    )

    explicit_quantity = re.compile(
        r"(?i)\b(?:qty|quantity)"
        r"\s*[:=]?\s*(\d{1,5})"
        r"(?:\.00)?(?![\d.])"
    )

    column_quantity = re.compile(
        r"(?<![\d.])(\d{1,5})(?:\.00)?"
        r"[ \t]+\$[ \t]*"
        r"[0-9][0-9,]*\.\d{2}\b"
    )

    def valid_model(value):

        return (
            any(char.isalpha() for char in value)
            and any(char.isdigit() for char in value)
        )

    def find_model(line):

        match = explicit_model.search(line)

        if match:
            return match.group(1).upper()

        match = standalone_model.match(line)

        if match:

            value = match.group(1).upper()

            if valid_model(value):
                return value

        return None

    def make_row(model, serials, quantities):

        return {
            "model_number": model,
            "serial_number_candidates": _unique(serials),
            "quantity_candidates": _unique(quantities),
            "employee_confirmation_required": True,
            "status": "UNVERIFIED",
        }

    equipment = []

    model = None
    model_index = -1
    serials = []
    quantities = []

    def flush():

        if model is not None or serials:

            equipment.append(
                make_row(
                    model,
                    serials,
                    quantities,
                )
            )

    for index, line in enumerate(lines):

        serial = serial_pattern.search(line)

        next_model = None if serial else find_model(line)

        if next_model:

            flush()

            model = next_model
            model_index = index
            serials = []
            quantities = []

        quantity = explicit_quantity.search(line)

        if quantity is None and model is not None:

            quantity = column_quantity.search(line)

        if quantity and model is not None:

            # Keep quantity associations local to the model.
            # Never use quantities from distant invoice lines.

            if index - model_index <= 3:

                value = int(quantity.group(1))

                if value > 0:
                    quantities.append(value)

        if serial:

            if model is not None and index - model_index > 4:

                flush()

                model = None
                model_index = -1
                serials = []
                quantities = []

            if model is None and serials:

                flush()

                serials = []
                quantities = []

            serials.append(
                serial.group(1).upper()
            )

    flush()

    # Standalone model candidates can also be ordinary
    # material or stock codes. Retain these only when
    # supported by serial evidence or explicit model labels.

    explicit_models = {
        match.group(1).upper()
        for match in explicit_model.finditer(text)
    }

    return [
        row
        for row in equipment
        if row["serial_number_candidates"]
        or row["model_number"] in explicit_models
    ]


def extract_invoice_text(text):

    if not isinstance(text, str):
        raise InvoiceExtractionError(
            "Invoice text is unavailable."
        )

    if len(text) > MAX_TEXT_LENGTH:
        raise InvoiceExtractionError(
            "Invoice text exceeds the review limit."
        )

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    invoice_numbers = re.findall(
        r"(?im)(?:^|[ \t]{2,})invoice[ \t]*"
        r"(?:number|no\.?|#)[ \t]*:?[ \t]*"
        r"([A-Z0-9][A-Z0-9._/-]{0,149})"
        r"[ \t|]*$",
        text,
    )

    distributors = re.findall(
        r"(?im)^\s*(?:distributor|supplier|vendor)"
        r"\s*:\s*([^\n]{1,250})$",
        text,
    )

    equipment = _equipment_candidates(text)

    fields = {
        "distributor_name": _suggest([
            value.strip() for value in distributors
        ]),
        "invoice_number": _suggest(invoice_numbers),
        "invoice_date": _suggest(_date_candidates(text)),
        "invoice_total": _suggest(_total_candidates(text)),
    }

    warnings = []

    for name, field in fields.items():

        if field["status"] != "SUGGESTED":
            warnings.append(
                name.replace("_", " ")
                + " requires employee review."
            )

    if not equipment:
        warnings.append(
            "Equipment identification requires employee review."
        )

    warnings.append(
        "Confirm that this is a distributor invoice issued to GECC."
    )

    warnings.append(
        "Confirm all model, serial number and quantity associations "
        "against the original document."
    )

    return {
        "fields": fields,
        "equipment_candidates": equipment,
        "warnings": warnings,
        "review_text": text,
        "employee_confirmation_required": True,
        "distributor_invoice_confirmed": False,
        "project_cost_allocation_confirmed": False,
        "approved_msr_match_confirmed": False,
        "purchase_verification_established": False,
        "payment_verified": False,
        "customer_selling_price_changed": False,
        "customer_document_release_authorized": False,
        "financial_posting_authorized": False,
    }


def _read_image(content, content_type):

    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise InvoiceExtractionError(
            "Local image processing is unavailable."
        ) from None

    expected_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
    }[content_type]

    executable = find_tesseract()

    if executable is None:
        raise InvoiceExtractionError(
            "Local invoice reading is unavailable. "
            "Enter the invoice information manually."
        )

    try:

        with Image.open(io.BytesIO(content)) as image:

            if image.format != expected_format:
                raise InvoiceExtractionError(
                    "Invoice image format does not match."
                )

            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise InvoiceExtractionError(
                    "Invoice image exceeds the allowed resolution."
                )

            image.verify()

        with Image.open(io.BytesIO(content)) as image:

            normalized = ImageOps.exif_transpose(
                image
            ).convert("RGB")

            normalized.thumbnail((3500, 3500))

            with tempfile.TemporaryDirectory(
                prefix="veridian-invoice-"
            ) as folder:

                image_path = Path(folder) / "invoice.png"

                normalized.save(
                    image_path,
                    format="PNG",
                )

                completed = subprocess.run(
                    [
                        executable,
                        str(image_path),
                        "stdout",
                        "-l", "eng",
                        "--psm", "3",
                        "-c", "preserve_interword_spaces=1",
                    ],
                    capture_output=True,
                    timeout=30,
                    check=False,
                    shell=False,
                )

                if completed.returncode != 0:
                    raise InvoiceExtractionError(
                        "Invoice image could not be read."
                    )

                text = completed.stdout.decode(
                    "utf-8",
                    errors="replace",
                )

                if len(text) > MAX_TEXT_LENGTH:
                    raise InvoiceExtractionError(
                        "Extracted invoice text is too large."
                    )

                return text

    except InvoiceExtractionError:
        raise

    except subprocess.TimeoutExpired:
        raise InvoiceExtractionError(
            "Invoice reading timed out. "
            "Try a clearer image or enter details manually."
        ) from None

    except (OSError, ValueError, Image.DecompressionBombError):
        raise InvoiceExtractionError(
            "Invoice image could not be safely processed."
        ) from None


def _read_pdf(content):

    try:
        from pypdf import PdfReader
    except ImportError:
        raise InvoiceExtractionError(
            "Local PDF text reading is unavailable."
        ) from None

    try:

        reader = PdfReader(
            io.BytesIO(content),
            strict=True,
        )

        if reader.is_encrypted:
            raise InvoiceExtractionError(
                "Password-protected invoices cannot be read."
            )

        if len(reader.pages) > MAX_PDF_PAGES:
            raise InvoiceExtractionError(
                "Invoice PDF exceeds the page limit."
            )

        pages = []
        characters = 0

        for page in reader.pages:

            value = page.extract_text() or ""
            characters += len(value)

            if characters > MAX_TEXT_LENGTH:
                raise InvoiceExtractionError(
                    "Invoice text exceeds the review limit."
                )

            pages.append(value)

        text = "\n".join(pages)

        if not text.strip():
            raise InvoiceExtractionError(
                "This PDF contains no readable text. "
                "Use a clear invoice image or enter details manually."
            )

        return text

    except InvoiceExtractionError:
        raise

    except Exception:
        raise InvoiceExtractionError(
            "Invoice PDF could not be read."
        ) from None


def extract_distributor_invoice(content, content_type):

    if (
        type(content) is not bytes
        or not content
        or len(content) > MAX_DOCUMENT_BYTES
    ):
        raise InvoiceExtractionError(
            "Choose an invoice file up to 15 MB."
        )

    signatures = {
        "application/pdf": b"%PDF-",
        "image/jpeg": bytes.fromhex("FFD8FF"),
        "image/png": bytes.fromhex("89504E470D0A1A0A"),
    }

    if (
        content_type not in signatures
        or not content.startswith(signatures[content_type])
    ):
        raise InvoiceExtractionError(
            "Choose a valid PDF, JPEG or PNG invoice."
        )

    if content_type == "application/pdf":

        text = _read_pdf(content)
        method = "LOCAL_PDF_TEXT"

    else:

        text = _read_image(content, content_type)
        method = "LOCAL_IMAGE_OCR"

    if not text.strip():
        raise InvoiceExtractionError(
            "No readable invoice information was found."
        )

    result = extract_invoice_text(text)

    result["document_sha256"] = sha256(content).hexdigest()
    result["extraction_method"] = method

    return result
