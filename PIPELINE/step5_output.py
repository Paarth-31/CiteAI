"""
step5_output.py
────────────────
STEP 5 — Output Renderer

Takes the fully-populated PipelineState and produces:

  • A colour-coded terminal report  (default)
  • A structured JSON file          (if out_path is given)

Public API
──────────
    run(state: PipelineState, out_path=None, json_stdout=False) -> None
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from models import PipelineState, VectorMatch, Conflict

# ── ANSI helpers (no external deps) ──────────────────────────────────────────

R  = "\033[0m"
B  = "\033[1m"
D  = "\033[2m"
GR = "\033[32m"
YE = "\033[33m"
RE = "\033[31m"
CY = "\033[36m"
MA = "\033[35m"
BL = "\033[34m"

def _cc(label: str) -> str:
    """Colour for HIGH / MEDIUM / LOW labels."""
    return {
        "HIGH":   GR,
        "MEDIUM": YE,
        "LOW":    RE,
    }.get(label, R)

def _coh_colour(label: str) -> str:
    return {
        "COHERENT":     GR,
        "MINOR_ISSUES": YE,
        "CONFLICTED":   RE,
    }.get(label, R)

def _bar(value: float, width: int = 24) -> str:
    filled = int(value * width)
    return "█" * filled + "░" * (width - filled)

def _hr(char: str = "─", width: int = 74) -> str:
    return char * width

def _trunc(text: str, n: int = 130) -> str:
    text = text.replace("\n", " ")
    return text[:n] + "…" if len(text) > n else text


# ── Section printers ──────────────────────────────────────────────────────────

def _print_header(state: PipelineState) -> None:
    cr = state.classifier_result
    total_time = sum(state.timings.values())

    print()
    print(f"{B}{_hr('═')}{R}")
    print(f"{B}  DocVerify — Verification Report{R}")
    print(f"{_hr('═')}")
    print(f"  {B}File{R}          {CY}{state.input_file}{R}")
    print(f"  {B}Total lines{R}   {state.total_lines}")
    print(f"  {B}Domain{R}        {B}{cr.domain.upper()}{R}  "
          f"({_bar(cr.confidence, 16)} {cr.confidence:.0%} confidence, "
          f"{cr.word_sample} words sampled)")
    print(f"  {B}Embedder{R}      {D}{cr.embedder_model}{R}")
    print(f"  {B}Total time{R}    {total_time:.2f}s  "
          f"{D}({', '.join(f'{k}: {v}s' for k, v in state.timings.items())}){R}")
    print(f"{_hr('═')}")


def _print_db_matches(state: PipelineState) -> None:
    matches = state.db_matches

    print(f"\n{B}  ┌─ SECTION 1 — VectorDB Corroboration ({'%d match' % len(matches)}{'es' if len(matches) != 1 else ''}) ─┐{R}")

    if not matches:
        print(f"\n  {YE}No matches above the similarity threshold.{R}\n")
        return

    # Group by confidence tier
    tiers = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for m in matches:
        tiers[m.match_confidence].append(m)

    for tier in ("HIGH", "MEDIUM", "LOW"):
        tier_matches = tiers[tier]
        if not tier_matches:
            continue
        colour = _cc(tier)
        print(f"\n  {colour}{B}  ▸ {tier} confidence  ({len(tier_matches)} match{'es' if len(tier_matches)!=1 else ''}){R}")

        for m in tier_matches:
            print()
            print(f"    {B}Lines {m.source_line_start}–{m.source_line_end}{R}")
            print(f"    {D}Source :{R} {_trunc(m.source_text)}")
            print(f"    {CY}DB doc :{R} {m.db_document}  [{D}{m.db_chunk_id}{R}]")
            print(f"    {D}DB text:{R} {_trunc(m.db_text)}")
            sim_str = f"{colour}{_bar(m.similarity)} {m.similarity:.4f}{R}"
            print(f"    Similarity : {sim_str}  [{colour}{B}{m.match_confidence}{R}]")


def _print_coherence(state: PipelineState) -> None:
    cr    = state.coherence_result
    color = _coh_colour(cr.coherence_label)

    print(f"\n{B}  ┌─ SECTION 2 — Intra-Document Coherence ─┐{R}\n")
    print(f"    {B}Score   :{R} {color}{_bar(cr.overall_coherence_score)} "
          f"{cr.overall_coherence_score:.4f}{R}")
    print(f"    {B}Verdict :{R} {color}{B}{cr.coherence_label}{R}")
    print(f"    {B}Chunks  :{R} {cr.total_chunks_examined}")
    print(f"    {B}Issues  :{R} {len(cr.conflicts)}")

    if not cr.conflicts:
        print(f"\n    {GR}✓ No internal conflicts detected.{R}\n")
        return

    # Group by type
    by_type: dict[str, list[Conflict]] = {}
    for c in cr.conflicts:
        by_type.setdefault(c.conflict_type, []).append(c)

    type_icons = {
        "SEMANTIC_CONTRADICTION": "⚡",
        "DUPLICATE":              "⎘",
        "NUMERICAL_MISMATCH":     "⚠",
    }
    type_colours = {
        "SEMANTIC_CONTRADICTION": MA,
        "DUPLICATE":              BL,
        "NUMERICAL_MISMATCH":     YE,
    }

    for ctype, items in by_type.items():
        icon   = type_icons.get(ctype, "•")
        tcolor = type_colours.get(ctype, R)
        print(f"\n  {tcolor}{B}  {icon} {ctype}  ({len(items)}){R}")

        for c in items[:5]:    # cap display at 5 per type
            sc = _cc(c.severity)
            print()
            print(f"    {B}Lines {c.line_a_start}–{c.line_a_end}{R}  ⟷  "
                  f"{B}Lines {c.line_b_start}–{c.line_b_end}{R}  "
                  f"[{sc}{B}{c.severity}{R}  score={c.score:.3f}]")
            print(f"    {D}A: {_trunc(c.text_a, 110)}{R}")
            print(f"    {D}B: {_trunc(c.text_b, 110)}{R}")
            print(f"    {D}→  {c.explanation}{R}")

        if len(items) > 5:
            print(f"    {D}… and {len(items)-5} more (see JSON output){R}")


def _print_footer(state: PipelineState) -> None:
    print()
    print(f"{_hr('═')}")
    print(f"{B}  End of Report{R}")
    print(f"{_hr('═')}\n")


# ── JSON serialiser ───────────────────────────────────────────────────────────

def _to_json(state: PipelineState) -> dict:
    from dataclasses import asdict
    d = state.to_dict()
    # Replace numpy-array placeholder with dimensions summary
    if d.get("embed_result"):
        er = state.embed_result
        d["embed_result"]["vectors_shape"] = list(er.vectors.shape)
    return d


# ── Public entry point ────────────────────────────────────────────────────────

def run(
    state:        PipelineState,
    out_path:     Path | None = None,
    json_stdout:  bool        = False,
) -> None:
    """
    Render the final report.

    Parameters
    ──────────
    state        : fully-populated PipelineState
    out_path     : if given, write JSON report to this path
    json_stdout  : if True, print JSON to stdout instead of pretty report
    """
    out_path = out_path or Path("outputs/report.json")

    if json_stdout:
        print(json.dumps(_to_json(state), indent=2))
    else:
        _print_header(state)
        _print_db_matches(state)
        _print_coherence(state)
        _print_footer(state)

    if out_path:
        out_path = Path(out_path)
        out_path.write_text(json.dumps(_to_json(state), indent=2))
        print(f"  {CY}Report saved → {out_path}{R}\n", file=sys.stderr)
