"""Controlled expansion of known equipment packages.

A package represents multiple individually identifiable equipment
components sold together as one system.

This module never modifies an approved MSR, guesses unknown package
contents, creates physical serial numbers or authorizes installation.
"""

from types import MappingProxyType


KNOWN_PACKAGE_COMPONENTS = MappingProxyType({
    "RA14AY36AJ1NA / RCFY3621STANMC / R802V1005A21UHSCAP": (
        ("RA14AY36AJ1NA", 1),
        ("RCFY3621STANMC", 1),
        ("R802V1005A21UHSCAP", 1),
    ),
})


def _package_key(model_number):

    return " / ".join(
        part.strip().upper()
        for part in model_number.split("/")
    )


def expand_purchase_requirement(
    *,
    model_number,
    quantity,
):

    if (
        type(model_number) is not str
        or not model_number.strip()
        or len(model_number) > 300
    ):
        raise ValueError(
            "Approved model identification is invalid."
        )

    if (
        type(quantity) is not int
        or not 1 <= quantity <= 999
    ):
        raise ValueError(
            "Approved equipment quantity is invalid."
        )

    model = model_number.strip()

    components = KNOWN_PACKAGE_COMPONENTS.get(
        _package_key(model)
    )

    if components is None:

        if "/" in model:

            raise ValueError(
                "A slash-separated model requires a confirmed "
                "equipment package definition before comparison."
            )

        return [{
            "model_number": model,
            "quantity": quantity,
        }]

    results = []

    seen = set()

    for component_model, units_per_package in components:

        normalized = component_model.casefold()

        if normalized in seen:

            raise ValueError(
                "Duplicate component in equipment package definition."
            )

        seen.add(normalized)

        if (
            not component_model
            or "/" in component_model
            or type(units_per_package) is not int
            or units_per_package < 1
        ):
            raise ValueError(
                "Invalid equipment package component."
            )

        results.append({
            "model_number": component_model,
            "quantity": quantity * units_per_package,
        })

    if not results:

        raise ValueError(
            "Equipment package contains no identifiable components."
        )

    return results
