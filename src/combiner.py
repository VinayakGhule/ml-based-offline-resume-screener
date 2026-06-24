






from __future__ import annotations

from datetime import date, datetime
from typing import Any

Candidate = dict[str, Any]


SKILL_WEIGHT  = 0.60
SIGNAL_WEIGHT = 0.40

assert abs(SKILL_WEIGHT + SIGNAL_WEIGHT - 1.0) < 1e-9




def _days_since(date_str: str) -> int:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - d).days
    except (ValueError, TypeError):
        return -1


def _penalty_multiplier(candidate: Candidate) -> float:
    
    signals  = candidate.get("redrob_signals", {})
    profile  = candidate.get("profile", {})
    multiplier = 1.0

    
    days = _days_since(signals.get("last_active_date", ""))
    if days > 180:
        multiplier *= 0.40
    elif days > 90:
        multiplier *= 0.70
    elif days > 60:
        multiplier *= 0.85

    
    rr = float(signals.get("recruiter_response_rate", 1.0))
    if rr < 0.10:
        multiplier *= 0.50
    elif rr < 0.20:
        multiplier *= 0.70

    
    icr = float(signals.get("interview_completion_rate", 1.0))
    if icr < 0.40:
        multiplier *= 0.65

    
    notice = int(signals.get("notice_period_days", 0))
    if notice > 90:
        multiplier *= 0.85

    
    salary = signals.get("expected_salary_range_inr_lpa", {})
    if salary.get("min", 0) > salary.get("max", 999):
        multiplier *= 0.10

    
    completeness = float(signals.get("profile_completeness_score", 100))
    if completeness < 30:
        multiplier *= 0.80

    return multiplier


def _experience_multiplier(candidate: Candidate, min_years: float = 3.0) -> float:
    
    yoe = float(candidate.get("profile", {}).get("years_of_experience", 0))
    if yoe >= min_years:
        return 1.0
    if yoe >= min_years - 1:
        return 0.85
    if yoe >= min_years - 2:
        return 0.65
    return 0.45




def combine_scores(
    candidate: Candidate,
    *,
    min_experience_years: float = 3.0,
) -> float:
    




    skill_score  = float(candidate.get("skill_score",  0.0))
    signal_score = float(candidate.get("signal_score", 0.0))

    raw = SKILL_WEIGHT * skill_score + SIGNAL_WEIGHT * signal_score
    raw *= _experience_multiplier(candidate, min_years=min_experience_years)
    raw *= _penalty_multiplier(candidate)

    return round(max(0.0, min(1.0, raw)), 6)