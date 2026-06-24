



















from __future__ import annotations

import argparse
import csv
import pickle
import time
from pathlib import Path
from typing import Any

ROOT               = Path(__file__).resolve().parent
DEFAULT_FEATURES   = ROOT / "data" / "precomputed" / "features.pkl"
DEFAULT_HONEYPOTS  = ROOT / "data" / "precomputed" / "honeypot_ids.txt"
DEFAULT_OUTPUT     = ROOT / "submission" / "team_xxx.csv"
DEFAULT_TOP_N      = 100

Candidate = dict[str, Any]




def _load_features(path: Path) -> list[Candidate]:
    with path.open("rb") as f:
        return pickle.load(f)


def _load_honeypot_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def _write_csv(ranked: list[Candidate], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["candidate_id", "rank", "score", "reasoning"]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in ranked:
            writer.writerow({
                "candidate_id": candidate["candidate_id"],
                "rank":         candidate["rank"],
                "score":        candidate["final_score"],
                "reasoning":    candidate["reasoning"],
            })




def _add_signal_scores(candidates: list[Candidate]) -> None:
    
    from src.signal_scorer import compute_signal_score
    for c in candidates:
        c["signal_score"] = compute_signal_score(c)


def _add_final_scores(candidates: list[Candidate]) -> None:
    
    from src.combiner import combine_scores
    for c in candidates:
        c["final_score"] = combine_scores(c)


def _filter_honeypots(
    candidates: list[Candidate],
    honeypot_ids: set[str],
) -> list[Candidate]:
    return [c for c in candidates if c.get("candidate_id") not in honeypot_ids]


def _add_reasoning(top_candidates: list[Candidate]) -> None:
    
    from src.reasoning import generate_reasoning
    for c in top_candidates:
        c["reasoning"] = generate_reasoning(c)




def rank(
    features_path: Path  = DEFAULT_FEATURES,
    honeypot_path: Path  = DEFAULT_HONEYPOTS,
    output_path: Path    = DEFAULT_OUTPUT,
    top_n: int           = DEFAULT_TOP_N,
) -> list[Candidate]:
    t0 = time.perf_counter()

    
    print("Loading features …")
    candidates    = _load_features(features_path)
    honeypot_ids  = _load_honeypot_ids(honeypot_path)
    print(f"  {len(candidates):,} candidates loaded | {len(honeypot_ids):,} honeypots flagged")

    
    print("Scoring behavioral signals …")
    _add_signal_scores(candidates)

    
    print("Combining scores …")
    _add_final_scores(candidates)

    
    clean = _filter_honeypots(candidates, honeypot_ids)
    removed = len(candidates) - len(clean)
    print(f"  Removed {removed:,} honeypot candidates")

    
    top = sorted(clean, key=lambda c: c["final_score"], reverse=True)[:top_n]

    
    for i, c in enumerate(top):
        c["rank"] = i + 1

    
    print("Generating reasoning …")
    _add_reasoning(top)

    
    print(f"Writing {output_path} …")
    _write_csv(top, output_path)

    elapsed = time.perf_counter() - t0
    print(f"\nTask completed in {elapsed:.1f}s — top {len(top)} candidates written to {output_path}")

    
    assert len(top) == top_n,                          f"Expected {top_n} rows, got {len(top)}"
    ranks = [c["rank"] for c in top]
    assert ranks == list(range(1, top_n + 1)),         "Ranks are not consecutive 1..N"
    scores = [c["final_score"] for c in top]
    assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1)), \
        "Scores are not non-increasing"

    return top




def main() -> None:
    parser = argparse.ArgumentParser(description="Rank candidates and write submission CSV.")
    parser.add_argument("--features",  type=Path, default=DEFAULT_FEATURES,  help="Path to features.pkl")
    parser.add_argument("--honeypots", type=Path, default=DEFAULT_HONEYPOTS, help="Path to honeypot_ids.txt")
    parser.add_argument("--out",       type=Path, default=DEFAULT_OUTPUT,    help="Output CSV path")
    parser.add_argument("--top",       type=int,  default=DEFAULT_TOP_N,     help="Number of candidates to rank")
    args = parser.parse_args()

    rank(
        features_path = args.features,
        honeypot_path = args.honeypots,
        output_path   = args.out,
        top_n         = args.top,
    )


if __name__ == "__main__":
    main()
