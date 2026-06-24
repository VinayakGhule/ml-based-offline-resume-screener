





















from __future__ import annotations

from datetime import date, datetime
from typing import Any

Candidate = dict[str, Any]




def _days_since(date_str: str) -> int:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - d).days
    except (ValueError, TypeError):
        return -1


def _graduation_year(candidate: Candidate) -> int | None:
    
    edu_list = candidate.get("education", [])
    years = [e.get("end_year") for e in edu_list if isinstance(e.get("end_year"), int)]
    return max(years) if years else None


def _assessment_scores(candidate: Candidate) -> list[float]:
    scores = candidate.get("redrob_signals", {}).get("skill_assessment_scores", {})
    return [float(v) for v in scores.values() if isinstance(v, (int, float))]


def _advanced_skill_count(candidate: Candidate) -> int:
    return sum(
        1 for s in candidate.get("skills", [])
        if s.get("proficiency") in ("advanced", "expert")
    )




def _impossible_salary(candidate: Candidate) -> bool:
    
    salary = candidate.get("redrob_signals", {}).get("expected_salary_range_inr_lpa", {})
    lo = salary.get("min", 0)
    hi = salary.get("max", 0)
    return isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi


def _impossible_experience(candidate: Candidate) -> bool:
    
    grad_year = _graduation_year(candidate)
    if grad_year is None:
        return False
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    max_possible = (date.today().year - grad_year) + 1
    return float(yoe) > max_possible


def _perfect_scores_no_activity(candidate: Candidate) -> bool:
    
    signals = candidate.get("redrob_signals", {})
    scores  = _assessment_scores(candidate)
    if not scores:
        return False
    all_perfect     = all(s >= 95 for s in scores)
    no_github       = signals.get("github_activity_score", -1) in (-1, 0)
    low_completeness = float(signals.get("profile_completeness_score", 100)) < 30
    return all_perfect and no_github and low_completeness


def _active_but_zero_response(candidate: Candidate) -> bool:
    

    signals      = candidate.get("redrob_signals", {})
    days         = _days_since(signals.get("last_active_date", ""))
    apps         = int(signals.get("applications_submitted_30d", 0))
    response_rate = float(signals.get("recruiter_response_rate", 1.0))
    return days != -1 and days <= 14 and apps >= 5 and response_rate == 0.0


def _all_assessment_scores_suspiciously_perfect(candidate: Candidate) -> bool:
    
    scores = _assessment_scores(candidate)
    return len(scores) > 3 and all(s >= 98 for s in scores)


def _advanced_skills_no_profile(candidate: Candidate) -> bool:
    
    signals     = candidate.get("redrob_signals", {})
    completeness = float(signals.get("profile_completeness_score", 100))
    advanced    = _advanced_skill_count(candidate)
    
    total_endorsements = sum(
        s.get("endorsements", 0)
        for s in candidate.get("skills", [])
        if s.get("proficiency") in ("advanced", "expert")
    )
    return completeness < 25 and advanced >= 4 and total_endorsements > 100


def _impossible_career_timeline(candidate: Candidate) -> bool:
    
    for job in candidate.get("career_history", []):
        start_str = job.get("start_date", "")
        end_str   = job.get("end_date", "")
        if not end_str:          
            continue
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end   = datetime.strptime(end_str,   "%Y-%m-%d").date()
            if end < start:
                return True
        except (ValueError, TypeError):
            continue
    return False


def _signup_after_last_active(candidate: Candidate) -> bool:
    
    signals     = candidate.get("redrob_signals", {})
    signup_str  = signals.get("signup_date", "")
    active_str  = signals.get("last_active_date", "")
    try:
        signup = datetime.strptime(signup_str, "%Y-%m-%d").date()
        active = datetime.strptime(active_str, "%Y-%m-%d").date()
        return signup > active
    except (ValueError, TypeError):
        return False


def _missing_candidate_id(candidate: Candidate) -> bool:
    cid = candidate.get("candidate_id", "")
    return not isinstance(cid, str) or not cid.strip()


def _career_history_contradicts_experience(candidate: Candidate) -> bool:
    years = float(candidate.get("profile", {}).get("years_of_experience", 0))
    documented_months = sum(
        int(role.get("duration_months") or 0)
        for role in candidate.get("career_history", [])
        if isinstance(role, dict)
    )
    return years >= 5 and documented_months <= 12


def _expert_skills_without_duration(candidate: Candidate) -> bool:
    expert_skills = [
        skill
        for skill in candidate.get("skills", [])
        if isinstance(skill, dict) and skill.get("proficiency") == "expert"
    ]
    short_duration = [
        skill for skill in expert_skills if int(skill.get("duration_months") or 0) <= 1
    ]
    return len(expert_skills) >= 5 and len(short_duration) >= 5


def _compound_profile_contradiction(candidate: Candidate) -> bool:
    if _impossible_career_timeline(candidate):
        return True
    career_contradiction = _career_history_contradicts_experience(candidate)
    skill_contradiction = _expert_skills_without_duration(candidate)
    metadata_contradictions = sum(
        (
            _impossible_salary(candidate),
            _signup_after_last_active(candidate),
            _impossible_experience(candidate),
        )
    )
    return (
        career_contradiction and (skill_contradiction or metadata_contradictions >= 1)
    ) or (skill_contradiction and metadata_contradictions >= 1)





_RULES: list[tuple] = [
    (_missing_candidate_id,                      "missing_candidate_id"),
    (_compound_profile_contradiction,             "compound_profile_contradiction"),
    (_perfect_scores_no_activity,                 "perfect_scores_no_activity"),
    (_all_assessment_scores_suspiciously_perfect, "all_assessments_perfect"),
    (_advanced_skills_no_profile,                 "advanced_skills_no_profile"),
]




def is_honeypot(candidate: Candidate) -> bool:
    
    return any(rule(candidate) for rule, _ in _RULES)


def honeypot_reason(candidate: Candidate) -> str | None:
    
    for rule, label in _RULES:
        if rule(candidate):
            return label
    return None


def find_honeypots(candidates: list[Candidate]) -> list[Candidate]:
    




    return [c for c in candidates if is_honeypot(c)]
