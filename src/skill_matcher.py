

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


SIMILARITY_THRESHOLD = 0.92


def _as_list(value: Any) -> list[Any]:
    
    return value if isinstance(value, list) else []


def _requirement_item(item: Any, priority: str) -> dict[str, str] | None:
    
    if isinstance(item, str):
        requirement = item.strip()
        normalized = ""
    elif isinstance(item, dict):
        requirement = str(item.get("requirement") or item.get("skill") or item.get("criterion") or "").strip()
        normalized = str(item.get("normalized_competency") or "").strip()
    else:
        return None
    if not requirement and not normalized:
        return None
    return {
        "requirement": requirement or normalized.replace("_", " "),
        "normalized_competency": normalized,
        "priority": priority,
    }


def extract_jd_capabilities(jd_intent: dict[str, Any]) -> list[dict[str, str]]:
    
    capabilities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    mandatory = jd_intent.get("mandatory_requirements", {})
    sources = (
        (_as_list(mandatory.get("skills")), "mandatory"),
        (_as_list(mandatory.get("experience_requirements")), "mandatory"),
        (_as_list(jd_intent.get("preferred_requirements", {}).get("skills")), "preferred"),
    )
    for items, priority in sources:
        for item in items:
            parsed = _requirement_item(item, priority)
            if not parsed:
                continue
            key = (parsed["normalized_competency"], parsed["requirement"].lower())
            if key in seen:
                continue
            seen.add(key)
            capabilities.append(parsed)

    if capabilities:
        return capabilities

    
    technical = jd_intent.get("technical_skills_inventory", {})
    for items in (_as_list(technical.get("skills")), _as_list(technical.get("technologies"))):
        for item in items:
            parsed = _requirement_item(item, "inventory")
            if parsed:
                capabilities.append(parsed)
    return capabilities


def _candidate_capability_index(candidate_capabilities: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    
    index: dict[str, dict[str, str]] = {}
    for capability in candidate_capabilities:
        normalized = str(capability.get("normalized_competency") or "").strip()
        if not normalized or normalized in index:
            continue
        index[normalized] = {
            "raw_phrase": str(capability.get("raw_phrase") or "").strip(),
            "normalized_competency": normalized,
            "source": str(capability.get("source") or "").strip(),
        }
    return index


def _find_match(
    jd_requirement: dict[str, str],
    candidate_index: dict[str, dict[str, str]],
) -> tuple[dict[str, str] | None, str]:
    
    normalized = jd_requirement.get("normalized_competency", "")
    if normalized and normalized in candidate_index:
        return candidate_index[normalized], "exact"

    if not normalized:
        return None, ""

    best_candidate: dict[str, str] | None = None
    best_ratio = 0.0
    for candidate_key, capability in candidate_index.items():
        ratio = SequenceMatcher(None, normalized, candidate_key).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_candidate = capability
    if best_candidate is not None and best_ratio >= SIMILARITY_THRESHOLD:
        return best_candidate, "similarity"
    return None, ""


def match_capabilities(
    jd_intent: dict[str, Any],
    candidate_capabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    
    jd_capabilities = extract_jd_capabilities(jd_intent)
    candidate_index = _candidate_capability_index(candidate_capabilities)

    matched: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    evidence: list[dict[str, str]] = []
    matched_weight = 0.0
    total_weight = 0.0

    for requirement in jd_capabilities:
        priority = requirement.get("priority", "mandatory")
        weight = 0.5 if priority == "preferred" else 1.0
        total_weight += weight
        candidate_match, match_type = _find_match(requirement, candidate_index)
        if candidate_match:
            matched_weight += weight
            row = {
                "requirement": requirement["requirement"],
                "normalized_competency": requirement["normalized_competency"],
                "candidate_phrase": candidate_match["raw_phrase"],
                "source": candidate_match["source"],
                "priority": priority,
                "match_type": match_type,
            }
            matched.append(row)
            evidence.append(row.copy())
        else:
            missing.append({
                "requirement": requirement["requirement"],
                "normalized_competency": requirement["normalized_competency"],
                "priority": priority,
            })

    skill_score = round((matched_weight / total_weight) * 10, 2) if total_weight else 0.0
    return {
        "skill_score": skill_score,
        "matched_capabilities": matched,
        "missing_capabilities": missing,
        "evidence": evidence,
    }


def extract_candidate_capabilities(candidate: dict[str, Any]) -> list[dict[str, str]]:
    
    capabilities: list[dict[str, str]] = []
    for skill in _as_list(candidate.get("skills")):
        if not isinstance(skill, dict):
            continue
        name = str(skill.get("name") or "").strip()
        normalized = str(skill.get("normalized_competency") or "").strip()
        if name and normalized:
            capabilities.append(
                {"raw_phrase": name, "normalized_competency": normalized, "source": "skills"}
            )
    return capabilities


def add_skill_scores(
    candidates: list[dict[str, Any]], jd_intent: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    





    intent = jd_intent or {}
    for candidate in candidates:
        result = match_capabilities(intent, extract_candidate_capabilities(candidate))
        candidate.update(result)
    return candidates


__all__ = [
    "add_skill_scores",
    "extract_candidate_capabilities",
    "extract_jd_capabilities",
    "match_capabilities",
]
