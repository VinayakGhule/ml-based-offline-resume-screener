
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


def _top_skills(candidate: Candidate, n: int = 3) -> list[str]:
    
    skills = candidate.get("skills", [])
    order  = {"expert": 0, "advanced": 1, "intermediate": 2, "beginner": 3}
    sorted_skills = sorted(
        skills,
        key=lambda s: (order.get(s.get("proficiency", "beginner"), 4),
                       -s.get("endorsements", 0))
    )
    return [s["name"] for s in sorted_skills[:n]]


def _activity_phrase(signals: dict) -> str:
    days = _days_since(signals.get("last_active_date", ""))
    if days < 0:
        return "activity unknown"
    if days <= 7:
        return "active this week"
    if days <= 30:
        return f"active {days} days ago"
    if days <= 90:
        return f"active ~{days // 30} month(s) ago"
    return f"last active {days} days ago"


def _response_phrase(signals: dict) -> str:
    rr = signals.get("recruiter_response_rate", None)
    if rr is None:
        return ""
    pct = int(float(rr) * 100)
    if pct >= 80:
        return f"highly responsive to recruiters ({pct}%)"
    if pct >= 50:
        return f"moderately responsive ({pct}% reply rate)"
    return f"low recruiter response rate ({pct}%)"


def _assessment_phrase(signals: dict) -> str:
    scores = signals.get("skill_assessment_scores", {})
    if not scores:
        return ""
    top_skill = max(scores, key=lambda k: scores[k])
    top_score = scores[top_skill]
    return f"verified {top_skill} score {top_score:.0f}/100"


def generate_reasoning(candidate: Candidate) -> str:
    
    profile  = candidate.get("profile", {})
    signals  = candidate.get("redrob_signals", {})

    headline = profile.get("headline", "").split("|")[0].strip()
    yoe      = profile.get("years_of_experience", 0)
    skills   = _top_skills(candidate)
    activity = _activity_phrase(signals)
    response = _response_phrase(signals)
    assess   = _assessment_phrase(signals)

    
    skill_str = ", ".join(skills) if skills else "relevant skills"
    sentence1 = (
        f"{headline} with {yoe:.1f} years of experience; "
        f"strong match on {skill_str}."
    )

    
    parts = [p for p in [activity, response, assess] if p]
    sentence2 = ("  " + "; ".join(parts).capitalize() + ".") if parts else ""

    return (sentence1 + sentence2).strip()