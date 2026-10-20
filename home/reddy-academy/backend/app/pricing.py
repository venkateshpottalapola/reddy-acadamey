"""
Transparent, configurable fee estimation for REDDY ACADEMY.
All pricing rules are documented inline. No arbitrary prices are invented.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# ── Grade tiers (monthly base fee, 3 classes/week, 1-hour sessions, one-to-one) ──
GRADE_BASE_FEE: dict[str, Decimal] = {
    "Nursery":                        Decimal("5000"),
    "LKG":                            Decimal("5000"),
    "UKG":                            Decimal("5000"),
    "Class 1":                        Decimal("6000"),
    "Class 2":                        Decimal("6000"),
    "Class 3":                        Decimal("6000"),
    "Class 4":                        Decimal("6000"),
    "Class 5":                        Decimal("6000"),
    "Class 6":                        Decimal("7500"),
    "Class 7":                        Decimal("7500"),
    "Class 8":                        Decimal("7500"),
    "Class 9":                        Decimal("9000"),
    "Class 10":                       Decimal("9000"),
    "Class 11":                       Decimal("11000"),
    "Class 12":                       Decimal("11000"),
    "Intermediate 1st Year":          Decimal("11000"),
    "Intermediate 2nd Year":          Decimal("11000"),
}

MAX_FEE_PER_STUDENT = Decimal("15000")

# ── Classes-per-week multipliers (base = 3 classes/week) ──
CLASSES_PER_WEEK_MULTIPLIER: dict[str, Decimal] = {
    "1 class":   Decimal("0.60"),
    "2 classes": Decimal("0.80"),
    "3 classes": Decimal("1.00"),
    "4 classes": Decimal("1.25"),
    "5 classes": Decimal("1.50"),
    "6 classes": Decimal("1.80"),
}

# ── Session-duration multipliers (base = 1 hour) ──
SESSION_DURATION_MULTIPLIER: dict[str, Decimal] = {
    "1 hour":            Decimal("1.00"),
    "1.5 hours":         Decimal("1.20"),
    "2 hours":           Decimal("1.40"),
    "To be discussed":   Decimal("1.00"),
}

# ── Tuition-type multipliers ──
TUITION_TYPE_MULTIPLIER: dict[str, Decimal] = {
    "One-to-one":       Decimal("1.00"),
    "Small group":      Decimal("0.80"),
    "To be discussed":  Decimal("1.00"),
    "":                 Decimal("1.00"),
}


@dataclass
class StudentFeeResult:
    grade: str
    base_fee: Optional[Decimal]
    classes_multiplier: Decimal
    duration_multiplier: Decimal
    tuition_multiplier: Decimal
    estimated_fee: Optional[Decimal]
    capped: bool
    status: str          # "estimated" | "unavailable"
    unavailable_reason: Optional[str]


def estimate_student_fee(
    grade: str,
    classes_per_week: Optional[str],
    session_duration: Optional[str],
    tuition_type: Optional[str],
) -> StudentFeeResult:
    base = GRADE_BASE_FEE.get(grade)
    if base is None:
        return StudentFeeResult(
            grade=grade,
            base_fee=None,
            classes_multiplier=Decimal("1"),
            duration_multiplier=Decimal("1"),
            tuition_multiplier=Decimal("1"),
            estimated_fee=None,
            capped=False,
            status="unavailable",
            unavailable_reason=f'Fee estimation is not available for "{grade}". '
                               "Submit the enquiry and REDDY ACADEMY will confirm the fee.",
        )

    cpw_key = classes_per_week or "3 classes"
    dur_key = session_duration or "1 hour"
    tut_key = tuition_type or ""

    cpw_mult = CLASSES_PER_WEEK_MULTIPLIER.get(cpw_key)
    if cpw_mult is None:
        cpw_mult = Decimal("1.00")

    dur_mult = SESSION_DURATION_MULTIPLIER.get(dur_key)
    if dur_mult is None:
        dur_mult = Decimal("1.00")

    tut_mult = TUITION_TYPE_MULTIPLIER.get(tut_key)
    if tut_mult is None:
        tut_mult = Decimal("1.00")

    raw = base * cpw_mult * dur_mult * tut_mult
    raw = raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    capped = raw > MAX_FEE_PER_STUDENT
    final = min(raw, MAX_FEE_PER_STUDENT)

    return StudentFeeResult(
        grade=grade,
        base_fee=base,
        classes_multiplier=cpw_mult,
        duration_multiplier=dur_mult,
        tuition_multiplier=tut_mult,
        estimated_fee=final,
        capped=capped,
        status="estimated",
        unavailable_reason=None,
    )


@dataclass
class HouseholdFeeResult:
    students: list[StudentFeeResult]
    individual_subtotal: Optional[Decimal]   # sum of each student's estimated fee
    combined_monthly_fee: Optional[Decimal]  # household total (no sibling discount configured)
    all_estimated: bool
    any_unavailable: bool
