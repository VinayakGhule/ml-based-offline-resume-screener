

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "candidates.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "precomputed" / "features.pkl"
DEFAULT_HONEYPOTS = ROOT / "data" / "precomputed" / "honeypot_ids.txt"
DEFAULT_JD = ROOT / "data" / "job_description.docx"
DEFAULT_JD_OUTPUT = ROOT / "data" / "precomputed" / "jd_intent.json"
Candidate = dict[str, Any]


def _normalise_honeypot_ids(result: Iterable[str | Candidate]) -> set[str]:
    ids: set[str] = set()
    for item in result:
        candidate_id = item.get("candidate_id") if isinstance(item, dict) else item
        if isinstance(candidate_id, str) and candidate_id:
            ids.add(candidate_id)
    return ids


def precompute(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
    honeypot_path: Path = DEFAULT_HONEYPOTS,
    jd_path: Path = DEFAULT_JD,
    jd_output_path: Path = DEFAULT_JD_OUTPUT,
) -> tuple[int, int]:
    
    
    from src.loader import load_candidates
    from src.filter import filter_invalid_candidates
    from src.skill_matcher import add_skill_scores
    from src.honeypot_detector import find_honeypots
    from src.jd_parser import parse_jd

    if not jd_path.exists():
        raise FileNotFoundError(f"Job description not found: {jd_path}")
    jd_intent = parse_jd(jd_path)
    loaded_candidates = load_candidates(input_path)
    candidates: list[Candidate] = filter_invalid_candidates(loaded_candidates, jd_intent)
    scored_candidates: list[Candidate] | None = add_skill_scores(candidates, jd_intent)
    candidates = candidates if scored_candidates is None else scored_candidates
    honeypot_ids = _normalise_honeypot_ids(find_honeypots(candidates))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    honeypot_path.parent.mkdir(parents=True, exist_ok=True)
    jd_output_path.parent.mkdir(parents=True, exist_ok=True)
    jd_output_path.write_text(json.dumps(jd_intent, ensure_ascii=False, indent=2), encoding="utf-8")
    with output_path.open("wb") as destination:
        pickle.dump(candidates, destination, protocol=pickle.HIGHEST_PROTOCOL)
    honeypot_path.write_text("".join(f"{candidate_id}\n" for candidate_id in sorted(honeypot_ids)), encoding="utf-8")
    return len(loaded_candidates), len(candidates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute candidate features.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--honeypots", type=Path, default=DEFAULT_HONEYPOTS)
    parser.add_argument("--jd", type=Path, default=DEFAULT_JD)
    parser.add_argument("--jd-output", type=Path, default=DEFAULT_JD_OUTPUT)
    args = parser.parse_args()
    loaded_count, filtered_count = precompute(args.input, args.output, args.honeypots, args.jd, args.jd_output)
    honeypot_count = sum(1 for line in args.honeypots.read_text(encoding="utf-8").splitlines() if line.strip())
    print(
        f"Loaded {loaded_count:,} candidates; {filtered_count:,} passed JD filters; "
        f"{honeypot_count:,} honeypots flagged."
    )


if __name__ == "__main__":
    main()
