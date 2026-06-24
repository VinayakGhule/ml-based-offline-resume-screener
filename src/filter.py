

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .loader import normalize_competency


DEFAULT_FILTER_CONFIG: dict[str, Any] = {
    "experience": {"enabled": True, "tolerance_years_below": 0.0},
    "location": {"enabled": True, "allow_relocation": True},
    "notice_period": {"enabled": True, "max_days": None},
    "rejection_criteria": {"enabled": True, "enforce_caution": False},
}


def merge_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    
    merged = deepcopy(DEFAULT_FILTER_CONFIG)
    if config:
        for section, values in config.items():
            if isinstance(values, dict) and isinstance(merged.get(section), dict):
                merged[section].update(values)
            else:
                merged[section] = values
    return merged


def _parse_min_years(value: Any) -> float | None:
    
    if value is None:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    return float(match.group(1)) if match else None


def _parse_days(value: Any) -> int | None:
    
    if value is None:
        return None
    match = re.search(r"(\d{1,3})\s*days?", str(value), re.I)
    return int(match.group(1)) if match else None


def _candidate_text(candidate: dict[str, Any]) -> str:
    
    chunks = []
    profile = candidate.get("profile", {})
    for field in ("headline", "summary", "current_title", "current_industry"):
        chunks.append(str(profile.get(field, "")))
    for skill in candidate.get("skills", []):
        chunks.append(str(skill.get("name", "")))
    for role in candidate.get("career_history", []):
        for field in ("title", "industry", "description"):
            chunks.append(str(role.get(field, "")))
    return " ".join(chunks).lower()


def _required_phrase_from_rejection(criterion: str) -> str | None:
    
    patterns = (
        r"^\s*without\s+(.+)$",
        r"^\s*no\s+(.+)$",
        r"^\s*who\s+cannot\s+(.+)$",
        r"^\s*can't\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, criterion, re.I)
        if match:
            phrase = re.split(r"[.;]| but | and ", match.group(1), maxsplit=1)[0]
            return phrase.strip()
    return None



def _passes_experience(candidate: dict[str, Any], jd_intent: dict[str, Any], config: dict[str, Any]) -> bool:
    
    if not config["experience"]["enabled"]:
        return True
    stated = jd_intent.get("job_metadata", {}).get("experience_range", {}).get("stated_years")
    minimum = _parse_min_years(stated)
    if minimum is None:
        return True
    candidate_years = float(candidate.get("profile", {}).get("years_of_experience") or 0)
    tolerance = float(config["experience"].get("tolerance_years_below") or 0)
    return candidate_years + tolerance >= minimum


def _passes_location(candidate: dict[str, Any], jd_intent: dict[str, Any], config: dict[str, Any]) -> bool:
    
    if not config["location"]["enabled"]:
        return True
    location = jd_intent.get("job_metadata", {}).get("location", {})
    work_model = str(location.get("work_model") or "").lower()
    if work_model in {"remote", "flexible"}:
        return True
    cities = list(location.get("preferred_cities") or []) + list(location.get("acceptable_cities") or [])
    if not cities:
        return True
    candidate_location = str(candidate.get("profile", {}).get("location") or "").lower()
    if any(city.lower() in candidate_location for city in cities):
        return True
    return bool(config["location"].get("allow_relocation") and candidate.get("redrob_signals", {}).get("willing_to_relocate"))


def _passes_notice(candidate: dict[str, Any], jd_intent: dict[str, Any], config: dict[str, Any]) -> bool:
    
    if not config["notice_period"]["enabled"]:
        return True
    max_days = config["notice_period"].get("max_days")
    if max_days is None:
        notice = jd_intent.get("job_metadata", {}).get("notice_period", {})
        max_days = _parse_days(notice.get("ideal"))
    if max_days is None:
        return True
    candidate_days = candidate.get("redrob_signals", {}).get("notice_period_days")
    if candidate_days is None:
        return True
    return int(candidate_days) <= int(max_days)


def _passes_rejection_criteria(candidate: dict[str, Any], jd_intent: dict[str, Any], config: dict[str, Any]) -> bool:
    
    if not config["rejection_criteria"]["enabled"]:
        return True
    candidate_blob = _candidate_text(candidate)
    criteria = jd_intent.get("disqualifiers_rejection_criteria", {}).get("criteria", [])
    for criterion in criteria:
        severity = str(criterion.get("severity", "likely_reject"))
        if severity == "caution" and not config["rejection_criteria"].get("enforce_caution"):
            continue
        required_phrase = _required_phrase_from_rejection(str(criterion.get("criterion", "")))
        if not required_phrase:
            continue
        normalized_terms = normalize_competency(required_phrase).replace("_", " ").split()
        meaningful_terms = [t for t in normalized_terms if len(t) > 3]
        if meaningful_terms and not all(t in candidate_blob for t in meaningful_terms):
            return False
    return True


def passes_hard_filters(
    candidate: dict[str, Any],
    jd_intent: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> bool:
    
    merged = merge_config(config)
    return (
        _passes_experience(candidate, jd_intent, merged)
        and _passes_location(candidate, jd_intent, merged)
        and _passes_notice(candidate, jd_intent, merged)
        and _passes_rejection_criteria(candidate, jd_intent, merged)
    )


def filter_candidates(
    candidates: list[dict[str, Any]],
    jd_intent: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    
    return [c for c in candidates if passes_hard_filters(c, jd_intent, config)]


def filter_invalid_candidates(
    candidates: list[dict[str, Any]],
    jd_intent: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    





    candidate_dicts = [candidate for candidate in candidates if isinstance(candidate, dict)]
    return filter_candidates(candidate_dicts, jd_intent or {}, config)


__all__ = ["filter_invalid_candidates", "filter_candidates", "passes_hard_filters"]
