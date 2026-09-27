from datetime import date
from math import isfinite, pow
from typing import Any


class ProjectionInputError(ValueError):
    pass


_GROWTH_SCENARIOS = {
    "low_growth": 2.0,
    "mid_growth": 5.0,
    "high_growth": 8.0,
}
_ANNUITY_RATE_PERCENT = 5.0
_PAYMENT_MONTHS = {
    "monthly": tuple(range(1, 13)),
    "quarterly": (3, 6, 9, 12),
    "semiannual": (6, 12),
    "semi-annual": (6, 12),
    "annual": (12,),
    "annually": (12,),
    "yearly": (12,),
}


def calculate_projection(
    quotation: dict[str, Any], as_of: date | None = None
) -> dict[str, Any]:
    today = as_of or date.today()
    customer = _object(quotation.get("customer"), "customer")
    pension_plan = _object(quotation.get("pension_plan"), "pension_plan")
    transfer = _object(quotation.get("transfer"), "transfer")

    birth_date_value = customer.get("date_of_birth")
    if not isinstance(birth_date_value, str):
        raise ProjectionInputError("customer.date_of_birth must be an ISO date")
    try:
        birth_date = date.fromisoformat(birth_date_value)
    except ValueError as exc:
        raise ProjectionInputError(
            "customer.date_of_birth must be an ISO date"
        ) from exc

    current_age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    retirement_age = _integer(pension_plan.get("retirement_age"), "pension_plan.retirement_age")
    if retirement_age < current_age:
        raise ProjectionInputError("Retirement age cannot be earlier than current age")
    years_to_retirement = retirement_age - current_age
    months_to_retirement = years_to_retirement * 12
    months_to_age_75 = max(75 - current_age, 0) * 12

    starting_fund = _number(
        transfer.get("transfer_value_gbp"), "transfer.transfer_value_gbp"
    )
    if starting_fund < 0:
        raise ProjectionInputError("transfer.transfer_value_gbp cannot be negative")

    contribution_schedule = _contribution_schedule(
        pension_plan.get("contributions", []), customer
    )
    projection: dict[str, Any] = {
        "basis": (
            "Illustrative gross annual growth; no product charges or inflation adjustment. "
            "Tax-free cash is 25% without an allowance cap. Annual pension uses the "
            "fixed 5% annuity rate."
        ),
        "years_to_retirement": years_to_retirement,
        "annuity_rate_percent": _ANNUITY_RATE_PERCENT,
    }

    for scenario, annual_growth_percent in _GROWTH_SCENARIOS.items():
        monthly_growth = pow(1 + annual_growth_percent / 100, 1 / 12) - 1
        balance = starting_fund
        retirement_value = balance if months_to_retirement == 0 else None
        age_75_value = balance if months_to_age_75 == 0 else None
        final_month = max(months_to_retirement, months_to_age_75)

        for month in range(1, final_month + 1):
            balance *= 1 + monthly_growth
            if month <= months_to_retirement:
                balance += contribution_schedule[(month - 1) % 12]
            if month == months_to_retirement:
                retirement_value = balance
            if month == months_to_age_75:
                age_75_value = balance

        if retirement_value is None or age_75_value is None:
            raise ProjectionInputError("Unable to calculate projection term")

        tax_free_cash = retirement_value * 0.25
        projection[scenario] = {
            "annual_growth_rate_percent": annual_growth_percent,
            "projected_fund_value_at_retirement_gbp": round(retirement_value, 2),
            "annual_pension_estimate_gbp": round(
                (retirement_value - tax_free_cash) * _ANNUITY_RATE_PERCENT / 100, 2
            ),
            "tax_free_lump_sum_gbp": round(tax_free_cash, 2),
            "projected_fund_value_at_75_gbp": round(age_75_value, 2),
        }

    transfer["projected_fund_value_at_75_gbp"] = projection["mid_growth"][
        "projected_fund_value_at_75_gbp"
    ]
    return projection


def _contribution_schedule(
    contributions: Any, customer: dict[str, Any]
) -> list[float]:
    if not isinstance(contributions, list):
        raise ProjectionInputError("pension_plan.contributions must be a JSON array")

    schedule = [0.0] * 12
    for index, contribution_value in enumerate(contributions):
        contribution = _object(
            contribution_value, f"pension_plan.contributions[{index}]"
        )
        frequency = contribution.get("frequency")
        if not isinstance(frequency, str):
            raise ProjectionInputError(
                f"pension_plan.contributions[{index}].frequency is required"
            )
        months = _PAYMENT_MONTHS.get(frequency.casefold())
        if months is None:
            raise ProjectionInputError(
                f"Unsupported contribution frequency: {frequency}"
            )

        if "annual_amount_gbp" in contribution:
            annual_amount = _number(
                contribution["annual_amount_gbp"],
                f"pension_plan.contributions[{index}].annual_amount_gbp",
            )
            payment_amount = annual_amount / len(months)
        elif "fixed_amount_gbp" in contribution:
            payment_amount = _number(
                contribution["fixed_amount_gbp"],
                f"pension_plan.contributions[{index}].fixed_amount_gbp",
            )
        elif "percent_of_salary" in contribution:
            salary = _number(
                customer.get("annual_salary_gbp"), "customer.annual_salary_gbp"
            )
            percent = _number(
                contribution["percent_of_salary"],
                f"pension_plan.contributions[{index}].percent_of_salary",
            )
            payment_amount = salary * percent / 100 / len(months)
        else:
            raise ProjectionInputError(
                f"pension_plan.contributions[{index}] requires annual_amount_gbp, "
                "fixed_amount_gbp, or percent_of_salary"
            )

        if payment_amount < 0:
            raise ProjectionInputError("Contribution amounts cannot be negative")
        for month in months:
            schedule[month - 1] += payment_amount

    return schedule


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectionInputError(f"{field} must be a JSON object")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectionInputError(f"{field} must be a number")
    number = float(value)
    if not isfinite(number):
        raise ProjectionInputError(f"{field} must be finite")
    return number


def _integer(value: Any, field: str) -> int:
    number = _number(value, field)
    if not number.is_integer():
        raise ProjectionInputError(f"{field} must be a whole number")
    return int(number)