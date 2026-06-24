
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _as_text(value: Any, default: str = "") -> str:
    
    return value if isinstance(value, str) else default


def _as_list(value: Any) -> list[Any]:
    
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    
    return value if isinstance(value, dict) else {}


def _as_float(value: Any, default: float = 0.0) -> float:
    
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int_or_none(value: Any) -> int | None:
    
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


FILLER_WORDS = {
    "a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "with",
    "by", "from", "into", "across", "using", "use", "ability", "able",
    "strong", "good", "excellent", "deep", "solid", "hands", "is", "are",
    "required", "preferred", "would", "be", "plus", "prior", "at", "least",
    "experience", "background", "knowledge", "familiarity", "exposure", "building",
}


LEADING_ACTION_WORDS = {
    "built", "build", "designed", "design", "managed", "manage", "led", "lead",
    "owned", "own", "implemented", "implement", "developed", "develop",
    "operated", "operate", "maintained", "maintain", "created", "create",
    "delivered", "deliver", "drove", "drive", "handled", "handle", "coordinated",
    "coordinate", "produced", "produce", "reviewed", "review", "analyzed", "analyze",
    "analysed", "analyse", "optimized", "optimize", "optimised", "optimise",
    "improved", "improve", "wrote", "write", "architected", "architect",
    "deployed", "deploy", "automated", "automate",
}


SINGULAR_SUFFIXES = (
    ("negotiations", "negotiation"), ("escalations", "escalation"),
    ("reviews", "review"), ("contracts", "contract"),
    ("requirements", "requirement"), ("incidents", "incident"),
    ("threats", "threat"), ("customers", "customer"),
    ("candidates", "candidate"), ("pipelines", "pipeline"), ("models", "model"),
)


def _slug_word(word: str) -> str:
    
    lowered = word.lower().strip(".,:;!?()[]{}")
    for suffix, replacement in SINGULAR_SUFFIXES:
        if lowered == suffix:
            return replacement
    if lowered.endswith("ies") and len(lowered) > 4:
        return lowered[:-3] + "y"
    if lowered.endswith("sses") or lowered in {"systems", "operations"}:
        return lowered
    return lowered


def normalize_competency(value: str) -> str:
    
    cleaned = re.sub(r"[^A-Za-z0-9+#./ -]+", " ", value)
    words = [
        word.strip(".,:;!?()[]{}")
        for word in re.split(r"[\s/+-]+", cleaned)
        if word.strip(".,:;!?()[]{}")
    ]
    while words and words[0].lower() in LEADING_ACTION_WORDS:
        words.pop(0)
    normalized_words = [
        _slug_word(word)
        for word in words
        if word.lower() not in FILLER_WORDS
    ]
    key = "_".join(normalized_words)
    return re.sub(r"_+", "_", key).strip("_")



def _validate_record(record: Any) -> tuple[bool, str | None]:
    
    if not isinstance(record, dict):
        return False, "not a dict"
    required_fields = ("candidate_id", "profile", "career_history", "skills", "redrob_signals")
    if not all(field in record for field in required_fields):
        return False, f"missing required fields"
    if not record.get("candidate_id"):
        return False, "empty candidate_id"
    return True, None


def _normalize_candidate(record: dict[str, Any]) -> dict[str, Any]:
    
    profile = _as_dict(record.get("profile", {}))
    signals = _as_dict(record.get("redrob_signals", {}))

    
    skills = []
    for skill in _as_list(record.get("skills", [])):
        if isinstance(skill, dict):
            name = _as_text(skill.get("name", "")).strip()
            if name:
                skills.append({
                    "name": name,
                    "normalized_competency": normalize_competency(name),
                    "proficiency": _as_text(skill.get("proficiency", "")),
                    "endorsements": _as_int_or_none(skill.get("endorsements")) or 0,
                    "duration_months": _as_int_or_none(skill.get("duration_months")),
                })

    
    career_history = []
    for role in _as_list(record.get("career_history", [])):
        if isinstance(role, dict):
            career_history.append({
                "company": _as_text(role.get("company", "")),
                "title": _as_text(role.get("title", "")),
                "start_date": _as_text(role.get("start_date", "")),
                "end_date": _as_text(role.get("end_date", "")),
                "industry": _as_text(role.get("industry", "")),
                "duration_months": _as_int_or_none(role.get("duration_months")) or 0,
                "is_current": bool(role.get("is_current")),
                "description": _as_text(role.get("description", "")),
            })

    return {
        "candidate_id": record["candidate_id"],
        "profile": {
            "anonymized_name": _as_text(profile.get("anonymized_name", "")),
            "headline": _as_text(profile.get("headline", "")),
            "summary": _as_text(profile.get("summary", "")),
            "location": _as_text(profile.get("location", "")),
            "country": _as_text(profile.get("country", "")),
            "years_of_experience": _as_float(profile.get("years_of_experience", 0.0)),
            "current_title": _as_text(profile.get("current_title", "")),
            "current_company": _as_text(profile.get("current_company", "")),
            "current_industry": _as_text(profile.get("current_industry", "")),
        },
        "career_history": career_history,
        "education": _as_list(record.get("education", [])),
        "skills": skills,
        "redrob_signals": {
            **signals,
            "notice_period_days": _as_int_or_none(signals.get("notice_period_days")),
            "preferred_work_mode": _as_text(signals.get("preferred_work_mode", "")),
            "willing_to_relocate": bool(signals.get("willing_to_relocate")),
            "open_to_work_flag": bool(signals.get("open_to_work_flag")),
        },
        "raw": record,
    }


def load_candidates(
    path: str | Path,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    
    candidates: list[dict[str, Any]] = []
    emitted = 0

    source_path = Path(path)
    if source_path.suffix.lower() == ".json":
        with source_path.open("r", encoding="utf-8") as handle:
            records = json.load(handle)
        if not isinstance(records, list):
            raise ValueError("JSON candidate input must contain a list of candidates")
        for record in records:
            if limit is not None and emitted >= limit:
                break
            valid, _ = _validate_record(record)
            if valid:
                candidates.append(_normalize_candidate(record))
                emitted += 1
        return candidates

    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if limit and emitted >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            valid, _ = _validate_record(record)
            if not valid:
                continue
            
            candidates.append(_normalize_candidate(record))
            emitted += 1

    return candidates

