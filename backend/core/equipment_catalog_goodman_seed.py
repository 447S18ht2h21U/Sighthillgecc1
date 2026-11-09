"""Goodman starter catalog from user-supplied PDF dated 2026-10-31.

Source entries are transcribed, not independently manufacturer-verified.
Flagged entries remain in the source but are not automatically imported.
Operational catalog imports are not enabled by any route or command.
"""

from dataclasses import dataclass
from django.db import transaction

from .equipment_catalog_service import create_equipment
from .models import EquipmentCatalogItem


@dataclass(frozen=True)
class GoodmanSourceRow:
    system_type: str
    model_number: str
    description: str
    review_required: bool = False


SOURCE_ROWS = (
    GoodmanSourceRow("Split Systems 7 Air Conditioners (R-32)", "GXV9S", "Up to 19.0 SEER2"),
    GoodmanSourceRow("Split Systems 7 Air Conditioners (R-32)", "GLXT7C", "Up to 17.2 SEER2"),
    GoodmanSourceRow("Split Systems 7 Air Conditioners (R-32)", "GXV6S", "Up to 17.2 SEER2"),
    GoodmanSourceRow("Split Systems 7 Air Conditioners (R-32)", "GLXS5B", "Up to 16.5 SEER2"),
    GoodmanSourceRow("Split Systems 7 Air Conditioners (R-32)", "GLXS4M", "Up to 15.2 SEER2"),
    GoodmanSourceRow("Split Systems 7 Air Conditioners (R-32)", "GLXS4B", "Up to 15.2 SEER2"),
    GoodmanSourceRow("Split Systems 7 Air Conditioners (R-32)", "GLXS3B", "Up to 15 SEER2"),
    GoodmanSourceRow("Heat Pumps (R-32)", "GZV9S", "Up to 21.0 SEER2 | Up to 10.0 HSPF2"),
    GoodmanSourceRow("Heat Pumps (R-32)", "GZV7S", "Up to 19.0 SEER2 | Up to 8.8 HSPF2"),
    GoodmanSourceRow("Heat Pumps (R-32)", "GZV6S", "Up to 19.0 SEER2 | Up to 8.8 HSPF2"),
    GoodmanSourceRow("Heat Pumps (R-32)", "GLZT7B", "Up to 17.5 SEER2 | Up to 8.2 HSPF2"),
    GoodmanSourceRow("Heat Pumps (R-32)", "GLZS5B", "Up to 16 SEER2 | Up to 8.2 HSPF2"),
    GoodmanSourceRow("Heat Pumps (R-32)", "GLZS4M", "Up to 15.2 SEER2 | Up to 7.8 HSPF2"),
    GoodmanSourceRow("Heat Pumps (R-32)", "GLZS4B", "Up to 15.2 SEER2 | Up to 7.8 HSPF2"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GRVM97", "Up to 97% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GDVM97", "97% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GRVT96", "Up to 97.5% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GDVT96", "Up to 97.5% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GRVS96-U", "Up to 96% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GR9S96-U", "Up to 92% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "CDVS96", "Up to 96% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GR9T96", "Up to 96% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GD9T96", "Up to 96% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GR9S96", "Up to 97% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GD9S96", "Up to 96% AFUE"),
    GoodmanSourceRow("Gas Furnaces 90+% AFUE Gas Furnaces (R-32)", "GR9S92", "Up to 92% AFUE"),
    GoodmanSourceRow("80% AFUE Gas Furnaces (R-32)", "GRVT80", "80% AFUE"),
    GoodmanSourceRow("80% AFUE Gas Furnaces (R-32)", "GDVT80", "80% AFUE"),
    GoodmanSourceRow("80% AFUE Gas Furnaces (R-32)", "GRVS80-U", "80% AFUE"),
    GoodmanSourceRow("80% AFUE Gas Furnaces (R-32)", "GR9S80-U", "80% AFUE"),
    GoodmanSourceRow("80% AFUE Gas Furnaces (R-32)", "GR9T80", "80% AFUE"),
    GoodmanSourceRow("80% AFUE Gas Furnaces (R-32)", "GD9T80", "80% AFUE"),
    GoodmanSourceRow("80% AFUE Gas Furnaces (R-32)", "GR9S80", "80% AFUE"),
    GoodmanSourceRow("80% AFUE Gas Furnaces (R-32)", "GD9S80", "80% AFUE"),
    GoodmanSourceRow("Air Handlers (R-32)", "AHVE (230V)", "Multi-Position, Variable-Speed"),
    GoodmanSourceRow("Air Handlers (R-32)", "AHVE (115V)", "Multi-Position, Variable-Speed"),
    GoodmanSourceRow("Air Handlers (R-32)", "AMST*13", "Multi-Position"),
    GoodmanSourceRow("Air Handlers (R-32)", "AWST*13", "Wall-Mount"),
    GoodmanSourceRow("Air Handlers (R-32)", "AMVT*13", "Multi-Position, Variable-Speed"),
    GoodmanSourceRow("Air Handlers (R-32)", "ACST*13", "Ceiling-Mount"),
    GoodmanSourceRow("Air Handlers (R-32)", "MBVK*H", "Multi-Position Modular Blowers"),
    GoodmanSourceRow("Evaporator Coils (R-32)", "CAPFA*3", 'Cased Indoor "A" Coil, Upflow/Downflow'),
    GoodmanSourceRow("Evaporator Coils (R-32)", "CAHEA", 'Cased Indoor "A" Coil, Multi-Position'),
    GoodmanSourceRow("Evaporator Coils (R-32)", "CAPTA*3", 'Cased Indoor "A" Coil, Upflow/Downflow'),
    GoodmanSourceRow("Evaporator Coils (R-32)", "CHPTA*3", 'Cased Indoor "A" Coil, Horizontal'),
    GoodmanSourceRow("Evaporator Coils (R-32)", "CAPEA*3**", "Cased Indoor Coil, Upflow/Downflow"),
    GoodmanSourceRow("Evaporator Coils (R-32)", "CHPEA*3**", "CHPEA*3** Cased Indoor Coil, Horizontal", True),
    GoodmanSourceRow("Evaporator Coils (R-32)", "CAUTA", "Uncased Indoor Coil, Upflow/Downflow"),
    GoodmanSourceRow("Evaporator Coils (R-32)", "CSCT", "Cased Indoor Coil, Horizontal Slab"),
    GoodmanSourceRow("Packaged Units AC (R-32)", "GPCH3", "Up to 13.4 SEER2"),
    GoodmanSourceRow("Packaged Units AC (R-32)", "GPCM3", "Up to 13.4 SEER2"),
    GoodmanSourceRow("Packaged Units Heat Pumps (R-32)", "GPHH5", "Up to 15.2 SEER2 | 6.7 HSPF2"),
    GoodmanSourceRow("Packaged Units Heat Pumps (R-32)", "GPHM5", "Up to 15.2 SEER2 | 6.7 HSPF2 G", True),
    GoodmanSourceRow("Packaged Units Heat Pumps (R-32)", "PHH3", "Up to 13.4 SEER2 | 6.7 HSPF2", True),
    GoodmanSourceRow("Packaged Units Heat Pumps (R-32)", "GPHM3", "Up to 13.4 SEER2 | 6.7 HSPF2"),
    GoodmanSourceRow("Packaged Units Gas/Electric (R-32)", "GPGM5", "Up to 15.2 SEER | 81% AFUE"),
    GoodmanSourceRow("Packaged Units Gas/Electric (R-32)", "GPGM3", "Up to 13.4 SEER2 | 81% AFUE"),
    GoodmanSourceRow("Packaged Units Gas/Electric (R-32)", "GPUM3", "Up to 13.4 SEER2 | 81% AFUE"),
)

REVIEW_ROWS = tuple(row for row in SOURCE_ROWS if row.review_required)
IMPORT_ROWS = tuple(row for row in SOURCE_ROWS if not row.review_required)


def row_details(row):
    return {
        "brand": "Goodman",
        "residential_system_type": row.system_type,
        "model_number": row.model_number,
        "description": row.description,
    }


@transaction.atomic
def import_verified_goodman_rows(*, actor_id):
    """Import unflagged rows once, with individual audited transactions.

    This function does not certify manufacturer specifications; it only
    excludes explicitly questionable transcription entries.
    """
    imported = 0
    existing = 0
    for row in IMPORT_ROWS:
        details = row_details(row)
        matches = EquipmentCatalogItem.objects.filter(
            brand=details["brand"],
            residential_system_type=details["residential_system_type"],
            model_number=details["model_number"],
        )
        if matches.exists():
            if not matches.filter(
                description=details["description"],
                is_active=True,
            ).exists():
                raise ValueError(
                    "Catalog identity already exists with different details: "
                    + row.model_number
                )
            existing += 1
            continue

        create_equipment(actor_id=actor_id, fields=details)
        imported += 1

    return {
        "created": imported,
        "already_present": existing,
        "review_required": len(REVIEW_ROWS),
    }