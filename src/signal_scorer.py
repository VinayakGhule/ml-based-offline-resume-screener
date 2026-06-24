









from __future__ import annotations

from datetime import date, datetime
from typing import Any

Candidate = dict[str, Any]


_WEIGHTS: dict[str, float] = {
    "recruiter_response_rate":   0.18,
    "interview_completion_rate": 0.14,
    "last_active_recency":       0.13,
    "avg_response_time_hours":   0.10,
    "open_to_work_flag":         0.08,
    "profile_completeness":      0.08,
    "offer_acceptance_rate":     0.07,
    "skill_assessment_avg":      0.07,
    "github_activity":           0.05,
    "notice_period":             0.04,
    "salary_reasonable":         0.03,
    "verified_contact":          0.02,
    "network_activity":          0.01,
}

assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"




def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _days_since(date_str: str) -> int:
    
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - d).days
    except (ValueError, TypeError):
        return -1




def _score_response_rate(signals: dict) -> float:
    v = signals.get("recruiter_response_rate", 0)
    return _clamp(float(v))


def _score_interview_completion(signals: dict) -> float:
    v = signals.get("interview_completion_rate", 0)
    return _clamp(float(v))


def _score_last_active(signals: dict) -> float:
    
    days = _days_since(signals.get("last_active_date", ""))
    if days < 0:
        return 0.0
    if days <= 7:
        return 1.0
    if days <= 30:
        return 0.85
    if days <= 60:
        return 0.65
    if days <= 90:
        return 0.40
    if days <= 180:
        return 0.20
    return 0.0


def _score_response_time(signals: dict) -> float:
    
    hours = float(signals.get("avg_response_time_hours", 240))
    return _clamp(1.0 - hours / 240.0)


def _score_open_to_work(signals: dict) -> float:
    return 1.0 if signals.get("open_to_work_flag") else 0.3


def _score_profile_completeness(signals: dict) -> float:
    v = float(signals.get("profile_completeness_score", 0))
    return _clamp(v / 100.0)


def _score_offer_acceptance(signals: dict) -> float:
    v = signals.get("offer_acceptance_rate", -1)
    if v == -1:          
        return 0.5
    return _clamp(float(v))


def _score_skill_assessments(signals: dict) -> float:
    scores = signals.get("skill_assessment_scores", {})
    if not scores:
        return 0.4       
    vals = [v for v in scores.values() if isinstance(v, (int, float))]
    if not vals:
        return 0.4
    avg = sum(vals) / len(vals)
    return _clamp(avg / 100.0)


def _score_github(signals: dict) -> float:
    v = signals.get("github_activity_score", -1)
    if v == -1:          
        return 0.3
    return _clamp(float(v) / 100.0)


def _score_notice_period(signals: dict) -> float:
    
    days = int(signals.get("notice_period_days", 90))
    return _clamp(1.0 - days / 180.0)


def _score_salary(signals: dict) -> float:
    
    salary = signals.get("expected_salary_range_inr_lpa", {})
    lo = salary.get("min", 0)
    hi = salary.get("max", 0)
    if lo > hi:          
        return 0.0
    return 0.7           


def _score_verified_contact(signals: dict) -> float:
    email = 1 if signals.get("verified_email") else 0
    phone = 1 if signals.get("verified_phone") else 0
    return (email + phone) / 2.0


def _score_network(signals: dict) -> float:
    
    connections = _clamp(float(signals.get("connection_count", 0)) / 1000.0)
    endorsements = _clamp(float(signals.get("endorsements_received", 0)) / 200.0)
    search = _clamp(float(signals.get("search_appearance_30d", 0)) / 500.0)
    return (connections + endorsements + search) / 3.0




_SCORERS = {
    "recruiter_response_rate":   _score_response_rate,
    "interview_completion_rate": _score_interview_completion,
    "last_active_recency":       _score_last_active,
    "avg_response_time_hours":   _score_response_time,
    "open_to_work_flag":         _score_open_to_work,
    "profile_completeness":      _score_profile_completeness,
    "offer_acceptance_rate":     _score_offer_acceptance,
    "skill_assessment_avg":      _score_skill_assessments,
    "github_activity":           _score_github,
    "notice_period":             _score_notice_period,
    "salary_reasonable":         _score_salary,
    "verified_contact":          _score_verified_contact,
    "network_activity":          _score_network,
}




def compute_signal_score(candidate: Candidate) -> float:
    
    signals = candidate.get("redrob_signals", {})
    total = 0.0
    for key, weight in _WEIGHTS.items():
        scorer = _SCORERS[key]
        total += weight * scorer(signals)
    return round(_clamp(total), 6)
