from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from .loader import normalize_competency


def read_docx(path: str | Path) -> str:
    with ZipFile(path) as archive:
        document = archive.read("word/document.xml")
    root = ElementTree.fromstring(document)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _requirement(name: str) -> dict[str, str]:
    return {"requirement": name, "normalized_competency": normalize_competency(name)}


def _section(text: str, start: str, endings: tuple[str, ...]) -> str:
    ending = "|".join(re.escape(value) for value in endings)
    match = re.search(rf"{re.escape(start)}\s*(.*?)(?={ending}|\Z)", text, re.I | re.S)
    return match.group(1).strip() if match else ""


def _split_items(value: str) -> list[str]:
    value = re.sub(r"\b(or|and) similar\b", "", value, flags=re.I)
    value = re.sub(r"\s+or\s+", ",", value, flags=re.I)
    parts = re.split(r"[,;]|\band\b", value, flags=re.I)
    return [re.sub(r"^[\s:—\-]+|[\s.]+$", "", part) for part in parts if part.strip()]


def _requirements(section: str) -> list[dict[str, str]]:
    items: list[str] = []
    for line in section.splitlines():
        for group in re.findall(r"\(([^()]+)\)", line):
            items.extend(_split_items(group))
        for group in re.findall(r"[—:]\s*([^.!]+)", line):
            items.extend(_split_items(group))
        direct = re.search(r"\b(?:strong|experience with|exposure to|background in)\s+([A-Za-z0-9+#./ -]+)", line, re.I)
        if direct:
            items.append(direct.group(1).split(".", 1)[0].strip())

    requirements: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        normalized = normalize_competency(item)
        if (
            not normalized
            or normalized in seen
            or normalized in {"something_similar", "neural"}
            or len(normalized.split("_")) > 5
        ):
            continue
        seen.add(normalized)
        requirements.append(_requirement(item))
    return requirements


def _location(text: str) -> tuple[str, list[str], list[str]]:
    match = re.search(r"^Location:\s*(.*?)(?:\||$)", text, re.I | re.M)
    location_line = match.group(1) if match else ""
    work_model = ""
    model = re.search(r"\b(hybrid|remote|onsite|on-site|flexible)\b", location_line, re.I)
    if model:
        work_model = model.group(1).lower().replace("-", "")
    first_part = re.split(r",\s*[A-Z][A-Za-z ]*(?:\(|$)", location_line, maxsplit=1)[0]
    preferred = [part.strip() for part in re.split(r"[/,]", first_part) if part.strip()]
    accepted = re.search(r"Candidates in\s+(.+?)\s+welcome", text, re.I)
    acceptable = _split_items(accepted.group(1)) if accepted else []
    acceptable = [place for place in acceptable if place.lower() not in {item.lower() for item in preferred}]
    return work_model, preferred, acceptable


def parse_jd(path: str | Path) -> dict:
    text = read_docx(path)
    experience = re.search(r"Experience Required:\s*(\d+)\s*[–-]\s*(\d+)\s*years", text, re.I)
    minimum_years = experience.group(1) if experience else None
    work_model, preferred_cities, acceptable_cities = _location(text)
    mandatory_section = _section(
        text,
        "Things you absolutely need",
        ("Things we'd like you to have", "Things we explicitly do NOT want", "On location"),
    )
    preferred_section = _section(
        text,
        "Things we'd like you to have",
        ("Things we explicitly do NOT want", "On location"),
    )
    disqualifier_section = _section(
        text,
        "Things we explicitly do NOT want",
        ("On location", "The vibe check", "How to read between the lines"),
    )
    return {
        "job_metadata": {
            "experience_range": {"stated_years": minimum_years},
            "location": {
                "work_model": work_model,
                "preferred_cities": preferred_cities,
                "acceptable_cities": acceptable_cities,
            },
            "notice_period": {},
        },
        "mandatory_requirements": {
            "skills": _requirements(mandatory_section),
            "experience_requirements": [],
        },
        "preferred_requirements": {
            "skills": _requirements(preferred_section),
        },
        "technical_skills_inventory": {},
        "disqualifiers_rejection_criteria": {
            "criteria": [{"criterion": line, "severity": "likely_reject"} for line in disqualifier_section.splitlines() if line],
        },
        "source_text": text,
    }
