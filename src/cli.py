"""Interactive runner: one insurance application through the underwriting pipeline."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from observability import configure_tracing
from pipeline import PipelineResult, run
from settings.config import Settings
from settings.factory import build_model, build_store

settings = Settings.from_env()

PRODUCTS = ("auto", "home", "life")


def print_decision(result: PipelineResult) -> None:
    """Print the final decision and the rationale when recommendation ran."""
    print("\n=== decision ===")
    print(f"Final Answer: {result.final_decision}")
    if result.recommendation is not None:
        print(f"Rationale: {result.recommendation.message.rationale}")
    print()


def _ask(label: str) -> str | None:
    """Read one field. None means the user quit."""
    try:
        value = input(f"{label}: ").strip()
    except EOFError:
        return None
    if value.lower() == "quit":
        return None
    return value


def _text(value: str) -> str | None:
    """Treat a blank name or address as missing."""
    if value.strip() == "":
        return None
    return value


def _date(value: str) -> str | None:
    """Keep an ISO date. Anything else is missing."""
    if value.strip() == "":
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _product(value: str) -> str | None:
    """Keep auto, home, or life. Anything else is missing."""
    lowered = value.strip().lower()
    if lowered in PRODUCTS:
        return lowered
    return None


def _money(value: str) -> float | None:
    """Keep a dollar amount rounded to cents. Anything else is missing."""
    if value.strip() == "":
        return None
    try:
        amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return float(amount)


def read_request() -> dict[str, Any] | None:
    """Prompt for one application. None means quit."""
    applicant_name = _ask("applicant_name")
    if applicant_name is None:
        return None
    date_of_birth = _ask("date_of_birth")
    if date_of_birth is None:
        return None
    address = _ask("address")
    if address is None:
        return None
    product = _ask("product")
    if product is None:
        return None
    coverage_amount = _ask("coverage_amount")
    if coverage_amount is None:
        return None
    stated_income = _ask("stated_income")
    if stated_income is None:
        return None
    return {
        "applicant_name": _text(applicant_name),
        "date_of_birth": _date(date_of_birth),
        "address": _text(address),
        "product": _product(product),
        "coverage_amount": _money(coverage_amount),
        "stated_income": _money(stated_income),
    }


def loop() -> None:
    """Reuse one model, store, and tracer until the user types quit."""
    model = build_model(settings)
    store = build_store(settings)
    tracer = configure_tracing()
    while True:
        application = read_request()
        if application is None:
            print("bye")
            break
        print(f"\n=== {application['applicant_name']} {application['product']} ===")
        print_decision(run(application, model, store, tracer))


def main() -> None:
    """Run applications until quit or Ctrl+C."""
    print("Type quit at any prompt to exit.")
    print("date_of_birth must be YYYY-MM-DD. product must be auto, home, or life.")
    try:
        loop()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()