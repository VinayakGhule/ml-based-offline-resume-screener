from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

import streamlit as st

from src.combiner import combine_scores
from src.filter import filter_invalid_candidates
from src.honeypot_detector import find_honeypots
from src.jd_parser import parse_jd
from src.loader import load_candidates
from src.reasoning import generate_reasoning
from src.signal_scorer import compute_signal_score
from src.skill_matcher import add_skill_scores


MAX_CANDIDATES = 100


def _write_upload(upload, directory: Path) -> Path:
    suffix = Path(upload.name).suffix.lower()
    path = directory / f"upload{suffix}"
    path.write_bytes(upload.getvalue())
    return path


def _csv_bytes(candidates: list[dict]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["candidate_id", "rank", "score", "reasoning"])
    writer.writeheader()
    for candidate in candidates:
        writer.writerow(
            {
                "candidate_id": candidate["candidate_id"],
                "rank": candidate["rank"],
                "score": candidate["final_score"],
                "reasoning": candidate["reasoning"],
            }
        )
    return output.getvalue().encode("utf-8")


def _rank(candidates: list[dict], jd_intent: dict) -> tuple[list[dict], int]:
    filtered = filter_invalid_candidates(candidates, jd_intent)
    scored = add_skill_scores(filtered, jd_intent)
    honeypot_ids = {candidate["candidate_id"] for candidate in find_honeypots(scored)}
    ranked = []
    for candidate in scored:
        if candidate["candidate_id"] in honeypot_ids:
            continue
        candidate["signal_score"] = compute_signal_score(candidate)
        candidate["final_score"] = combine_scores(candidate)
        ranked.append(candidate)
    ranked.sort(key=lambda candidate: candidate["final_score"], reverse=True)
    for rank, candidate in enumerate(ranked, start=1):
        candidate["rank"] = rank
        candidate["reasoning"] = generate_reasoning(candidate)
    return ranked, len(honeypot_ids)


st.set_page_config(page_title="Offline Resume Screener", page_icon="📄", layout="wide")
st.title("Offline Resume Screener")
st.write("Upload up to 100 candidate records and a job-description DOCX to generate a ranked CSV.")

candidate_upload = st.file_uploader("Candidate sample (.json or .jsonl)", type=["json", "jsonl"])
jd_upload = st.file_uploader("Job description (.docx)", type=["docx"])

if st.button("Rank candidates", type="primary"):
    if candidate_upload is None or jd_upload is None:
        st.error("Upload both a candidate sample and a job-description DOCX.")
    else:
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                directory = Path(temporary_directory)
                candidate_path = _write_upload(candidate_upload, directory)
                jd_path = _write_upload(jd_upload, directory)
                candidates = load_candidates(candidate_path)
                if not candidates:
                    raise ValueError("No valid candidate records were found.")
                if len(candidates) > MAX_CANDIDATES:
                    raise ValueError(f"Upload at most {MAX_CANDIDATES} candidates; received {len(candidates)}.")
                ranked, honeypot_count = _rank(candidates, parse_jd(jd_path))
        except Exception as error:
            st.error(str(error))
        else:
            st.success(
                f"Loaded {len(candidates)} candidates; ranked {len(ranked)}; "
                f"excluded {honeypot_count} suspected honeypot(s)."
            )
            rows = [
                {
                    "candidate_id": candidate["candidate_id"],
                    "rank": candidate["rank"],
                    "score": candidate["final_score"],
                    "reasoning": candidate["reasoning"],
                }
                for candidate in ranked
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.download_button(
                "Download ranked CSV",
                data=_csv_bytes(ranked),
                file_name="ranked_candidates.csv",
                mime="text/csv",
            )
