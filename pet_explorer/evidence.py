"""Sequence-based PET-degradation evidence assessment (green / yellow / red / insufficient).

This is a transparent, rule-based summary of measured sequence evidence. It is
NOT a machine-learning prediction and NOT a probability of PET activity.

What the rules use (all computed, nothing looked up by name)
-------------------------------------------------------------
For the top hit of the Smith-Waterman / BLOSUM62 search against the 298 curated
PET-active reference proteins (ranked by length-normalised score):

* identity            identical residues / aligned columns
* query / reference   aligned span / full length of each sequence
  coverage
* similarity band     config.MATCH_BANDS (identity AND coverage of both sequences)
* shuffle z           z-score of the raw score against N_SHUFFLES composition-preserving
                      shuffles of the query (same seed in every interface)
* G-x-S-x-G motif     catalytic-serine motif of alpha/beta-hydrolases in the query
* reference evidence  PET assays / publications / label confidence of the matched
                      reference protein (experimental evidence belongs to the reference)

Calibration of the z thresholds (see `python -m pet_explorer.evidence`)
-----------------------------------------------------------------------
* Null: every reference protein shuffled once (composition kept, order destroyed)
  and searched against the full set. Top-hit z: median 3.5, 99th percentile 9.0,
  maximum 10.2 (n = 298).
* True relatives: leave-one-out search of every reference protein with its own
  entry removed. Every twilight-band nearest neighbour had z >= 16.9; 295 of 298
  had z > 15.

Result of applying these rules to the calibration sets (outputs/explorer/matching/
evidence_calibration_summary.json):
* shuffled null (298):  294 red, 4 insufficient, 0 yellow, 0 green
* leave-one-out (298):  249 green, 43 yellow, 4 insufficient, 2 red

Hence Z_CHANCE = 9.0 (at or below this, the score looks like shuffled sequence)
and Z_STRONG = 15.0 (above every null draw with margin, below every twilight-band
true relative). Between the two, the score is ambiguous.

Why red is never "PET-inactive"
-------------------------------
The reference set contains only PET-active proteins; no validated PET-inactive
set exists. Red therefore means "no convincing similarity to characterised
PET-degrading enzymes", never "shown to be inactive". Leave-one-out shows that
a few genuinely PET-active proteins with no close relative in the set would also
be red (see the calibration summary), which is listed as a limitation.
"""

import json
import re
from typing import Optional

from . import config as C

RULES_VERSION = "1.0"

N_SHUFFLES = 25          # used by single-sequence and bulk analysis alike
SHUFFLE_SEED = 0
Z_CHANCE = 9.0           # 99th percentile of the shuffled-query null (top hit, n = 298)
Z_STRONG = 15.0          # above the null maximum (10.2), below the weakest twilight-band true relative (16.9)
FRAGMENT_REF_COVERAGE = 0.50
DOMAIN_REF_COVERAGE = 0.70

_GXSXG = re.compile(r"(?=(G.S.G))")

GREEN, YELLOW, RED, INSUFFICIENT = "green", "yellow", "red", "insufficient"
LABELS = {
    GREEN: "Likely PET-degrading candidate",
    YELLOW: "Possible PET-degrading candidate",
    RED: "Unlikely based on current evidence",
    INSUFFICIENT: "Insufficient evidence",
}

HOMOLOG_BANDS = {C.MATCH_BANDS[0][2], C.MATCH_BANDS[1][2]}
TWILIGHT_BAND = C.MATCH_BANDS[2][2]

GENERAL_LIMITATIONS = [
    "This is a sequence-based evidence assessment, not a validated prediction of PET-degrading activity.",
    "The reference set holds only PET-active proteins; there is no validated PET-inactive set to calibrate against, "
    "so no probability of activity can be given.",
    "Single substitutions near the active site can abolish activity while leaving sequence identity almost unchanged.",
    "Expression, folding, solubility and stability are not visible in a pairwise alignment.",
]


# ------------------------------------------------------------------ helpers

def motif_count(sequence: str) -> int:
    return len(_GXSXG.findall(sequence))


def tandem_repeat(sequence: str, max_period: int = 20, threshold: float = 0.8) -> Optional[int]:
    """Smallest period p <= max_period for which >= threshold of residues equal the residue p positions on.

    Flags synthetic or low-complexity repeats, for which alignment statistics are atypical.
    """
    n = len(sequence)
    for p in range(1, min(max_period, n // 3) + 1):
        same = sum(sequence[i] == sequence[i + p] for i in range(n - p))
        if same / (n - p) >= threshold:
            return p
    return None


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _ref_evidence_text(ref: dict) -> str:
    pubs = ref.get("n_publications") or 0
    return (f"{ref.get('n_positive_assays', 0)} of {ref.get('n_pet_assays', 0)} curated PET assays positive, "
            f"{pubs} publication{'s' if pubs != 1 else ''}; label: {ref.get('pet_label')} "
            f"({ref.get('label_confidence')} confidence)")


# ------------------------------------------------------------------ rules

RULES = [
    {"id": "K", "category": GREEN, "condition": "Identity = 100% and coverage = 100% of both sequences",
     "meaning": "The sequence IS a characterised reference protein; its published assays apply directly."},
    {"id": "H1", "category": GREEN,
     "condition": f"Identity >= 40% and coverage >= 70% of both sequences, shuffle z >= {Z_STRONG:g}, "
                  "G-x-S-x-G motif present, reference has >= 1 positive PET assay with high label confidence",
     "meaning": "Clear homolog of an experimentally characterised PET-degrading enzyme."},
    {"id": "H2", "category": YELLOW,
     "condition": "As H1, but the G-x-S-x-G motif is absent or the reference's own evidence is medium confidence",
     "meaning": "Homolog, but one supporting line of evidence is missing."},
    {"id": "H3", "category": INSUFFICIENT,
     "condition": f"Identity/coverage reach the homolog bands but shuffle z < {Z_STRONG:g}",
     "meaning": "Identity/coverage and the shuffle control disagree (typical of low-complexity sequence)."},
    {"id": "P", "category": YELLOW,
     "condition": f"Identity >= 40% but coverage of one sequence only 50-70%, shuffle z >= {Z_STRONG:g}",
     "meaning": "Close relative over part of the protein (truncation or different domain arrangement)."},
    {"id": "T1", "category": YELLOW,
     "condition": f"Twilight band (25-40% identity, coverage >= 50% of both) and shuffle z >= {Z_STRONG:g}",
     "meaning": "Possible distant homolog; identity alone cannot establish homology here."},
    {"id": "T2", "category": INSUFFICIENT,
     "condition": f"Twilight band and {Z_CHANCE:g} < shuffle z < {Z_STRONG:g}", "meaning": "Ambiguous similarity."},
    {"id": "T3", "category": RED, "condition": f"Twilight band and shuffle z <= {Z_CHANCE:g}",
     "meaning": "The score is within the range seen for shuffled sequences."},
    {"id": "D1", "category": YELLOW,
     "condition": f"No band, shuffle z >= {Z_STRONG:g}, >= {DOMAIN_REF_COVERAGE:.0%} of the reference but "
                  f"< {DOMAIN_REF_COVERAGE:.0%} of the query aligned",
     "meaning": "The query contains a region covering most of a PET enzyme (e.g. a multi-domain protein)."},
    {"id": "D2", "category": YELLOW,
     "condition": f"No band (identity < 25%), shuffle z >= {Z_STRONG:g}, coverage >= 50% of both sequences",
     "meaning": "Low identity but significant similarity over most of both sequences."},
    {"id": "F", "category": INSUFFICIENT,
     "condition": f"Identity >= 40%, >= 70% of the query aligned but < {FRAGMENT_REF_COVERAGE:.0%} of the reference",
     "meaning": "The query looks like a fragment of a PET enzyme; a partial sequence cannot be assessed."},
    {"id": "L", "category": INSUFFICIENT,
     "condition": f"No band, shuffle z >= {Z_STRONG:g}, but only a short local region aligns",
     "meaning": "Significant but short local similarity."},
    {"id": "N1", "category": INSUFFICIENT, "condition": f"No band and {Z_CHANCE:g} < shuffle z < {Z_STRONG:g}",
     "meaning": "Ambiguous similarity."},
    {"id": "N2", "category": RED, "condition": f"No band and shuffle z <= {Z_CHANCE:g}",
     "meaning": "No convincing similarity to any characterised PET-degrading enzyme."},
]
_RULE = {r["id"]: r for r in RULES}


def rules() -> dict:
    return {
        "version": RULES_VERSION,
        "n_shuffles": N_SHUFFLES,
        "z_chance": Z_CHANCE,
        "z_strong": Z_STRONG,
        "bands": [{"min_identity": i, "min_coverage": c, "label": l} for i, c, l in C.MATCH_BANDS],
        "rules": RULES,
        "calibration": calibration_summary(),
        "notes": [
            "Identity is never used alone: every rule combines identity, coverage of both sequences and the shuffle control.",
            "The catalytic motif can only lower an assessment (green -> yellow), never raise one.",
            "Protein names and file labels are never read by the rules.",
            "Colours describe sequence evidence; they are not validated predictions of PET-degrading activity.",
        ],
    }


def assess(top, reference: Optional[dict], sequence: str) -> dict:
    """Evidence assessment for one query.

    `top` is the best sequence_matching.Hit (or None); `reference` is the evidence
    card of that hit's reference protein (backend.services.store.protein_card).
    """
    motifs = motif_count(sequence)
    repeat = tandem_repeat(sequence)
    limitations = list(GENERAL_LIMITATIONS)
    if repeat:
        limitations.insert(0, f"The sequence is a near-perfect tandem repeat (period {repeat} aa), typical of synthetic "
                              "or low-complexity sequence; alignment statistics are less informative for such input.")

    if top is None or reference is None:
        return _result(INSUFFICIENT, "none", "No alignment could be computed.", [], limitations,
                       ["Check the sequence and run the analysis again."], None, motifs, repeat, False)

    I, qc, tc, z = top.identity, top.query_coverage, top.target_coverage, top.shuffled_z
    mc = min(qc, tc)
    band = top.interpretation
    name = top.protein_name
    ref_ok = (reference.get("n_positive_assays") or 0) >= 1 and reference.get("label_confidence") == "high"
    numbers = (f"Closest characterised enzyme: {name}. Identity {_pct(I)} over {top.aligned_columns} aligned columns; "
               f"coverage {_pct(qc)} of the query and {_pct(tc)} of {name}; shuffle z = {z:.1f}.")
    ref_text = f"Experimental evidence for {name} (the reference, not this query): {_ref_evidence_text(reference)}."
    motif_text = (f"G-x-S-x-G catalytic-serine motif found {motifs}x (consistent with an alpha/beta-hydrolase; "
                  "not proof of PET activity)." if motifs else
                  "No G-x-S-x-G catalytic-serine motif found (296 of the 298 PET-active references carry one).")
    reasons = [numbers, motif_text, ref_text]
    lab = ["Confirm activity experimentally (e.g. PET film or powder hydrolysis with HPLC quantification of TPA/MHET), "
           "including a known PET hydrolase as positive control."]

    if I == 1 and qc == 1 and tc == 1:
        rule = "K"
        summary = (f"Identical to {name}, an experimentally characterised PET-degrading enzyme in the reference set. "
                   "This is a known reference, not a newly predicted discovery.")
        next_steps = [f"Use the published assays for {name} (listed below) rather than re-predicting its activity.",
                      "Check that the assay conditions you need (substrate, temperature, pH) were actually tested."]
        cat = GREEN if ref_ok or (reference.get("n_positive_assays") or 0) >= 1 else YELLOW
        return _result(cat, rule, summary, reasons, limitations, next_steps, top, motifs, repeat, True)

    homolog = band in HOMOLOG_BANDS
    twilight = band == TWILIGHT_BAND
    homolog_caveat = ("High sequence similarity supports further investigation but does not prove PET activity "
                      "in a new protein.")

    if homolog:
        if z < Z_STRONG:
            rule, cat = "H3", INSUFFICIENT
            summary = (f"Identity and coverage reach the homolog bands for {name}, but the alignment score is not "
                       f"clearly above shuffled-sequence controls (z = {z:.1f} < {Z_STRONG:g}). The signals disagree.")
            next_steps = ["Inspect the sequence for low-complexity or repetitive regions.",
                          "Confirm the similarity with an independent method (e.g. BLASTP E-value or a profile HMM)."]
        elif not motifs:
            rule, cat = "H2", YELLOW
            summary = (f"Clear homolog of {name}, but the G-x-S-x-G catalytic-serine motif is missing, which may "
                       "indicate a substitution at the active site. " + homolog_caveat)
            next_steps = ["Check the alignment around the catalytic serine of the reference.", *lab]
        elif not ref_ok:
            rule, cat = "H2", YELLOW
            summary = (f"Clear homolog of {name}, but the reference's own PET evidence is limited "
                       f"({reference.get('label_confidence')} label confidence). " + homolog_caveat)
            next_steps = ["Look for a better-characterised relative among the other top hits.", *lab]
        else:
            rule, cat = "H1", GREEN
            summary = (f"Strong sequence evidence: {band.lower()} ({_pct(I)} identity over {_pct(mc)}+ of both "
                       f"sequences, z = {z:.1f}). " + homolog_caveat)
            next_steps = ["Prioritise for expression and PET-hydrolysis testing.",
                          "Compare active-site residues with the reference before testing.", *lab]
    elif twilight:
        if z >= Z_STRONG and I >= 0.40:
            rule, cat = "P", YELLOW
            summary = (f"{_pct(I)} identity to {name}, but the alignment covers only {_pct(qc)} of the query and "
                       f"{_pct(tc)} of {name} (homolog bands need >= 70% of both). It may be truncated or have a "
                       "different domain arrangement. " + homolog_caveat)
            next_steps = ["Check whether the sequence is full-length (start/stop, gene boundaries).", *lab]
        elif z >= Z_STRONG:
            rule, cat = "T1", YELLOW
            summary = (f"Possible distant homolog of {name}: {_pct(I)} identity is in the twilight zone, where "
                       f"identity alone cannot establish homology, although the score is well above shuffled "
                       f"controls (z = {z:.1f}).")
            next_steps = ["Confirm homology with a profile method (HMM search against the PET-hydrolase family) "
                          "or structure prediction.", *lab]
        elif z <= Z_CHANCE:
            rule, cat = "T3", RED
            summary = (f"Twilight-zone identity to {name}, but the alignment score is within the range seen for "
                       f"shuffled sequences (z = {z:.1f}). The sequence evidence does not support prioritising it.")
            next_steps = ["No follow-up suggested on sequence grounds. Laboratory testing would be needed to "
                          "establish activity either way."]
        else:
            rule, cat = "T2", INSUFFICIENT
            summary = (f"Twilight-zone identity to {name} with an ambiguous score (z = {z:.1f}, between "
                       f"{Z_CHANCE:g} and {Z_STRONG:g}). The evidence cannot be assigned a colour reliably.")
            next_steps = ["Use a more sensitive homology search (profile HMM) before deciding on lab work."]
    else:
        if z >= Z_STRONG and I >= 0.40 and qc >= 0.70 and tc < FRAGMENT_REF_COVERAGE:
            rule, cat = "F", INSUFFICIENT
            summary = (f"Looks like a fragment of a {name}-like enzyme: {_pct(I)} identity over most of the query, "
                       f"but only {_pct(tc)} of {name} is covered. A partial sequence cannot be assessed.")
            next_steps = ["Obtain the full-length sequence (check gene boundaries / assembly) and analyse it again."]
        elif z >= Z_STRONG and tc >= DOMAIN_REF_COVERAGE and qc < DOMAIN_REF_COVERAGE:
            rule, cat = "D1", YELLOW
            summary = (f"A region of this protein covers {_pct(tc)} of {name} with z = {z:.1f}, but the rest of the "
                       f"query ({_pct(1 - qc)}) is unaligned, e.g. a multi-domain protein.")
            next_steps = ["Identify the domain boundaries and consider expressing the PET-hydrolase-like domain.", *lab]
        elif z >= Z_STRONG and mc >= 0.50:
            rule, cat = "D2", YELLOW
            summary = (f"Low identity ({_pct(I)}) to {name}, but the alignment spans most of both sequences and is "
                       f"far above shuffled controls (z = {z:.1f}): a possible remote homolog.")
            next_steps = ["Confirm with a profile HMM search or structure prediction.", *lab]
        elif z >= Z_STRONG:
            rule, cat = "L", INSUFFICIENT
            summary = (f"Significant (z = {z:.1f}) but short local similarity to {name}: only {_pct(qc)} of the "
                       f"query and {_pct(tc)} of the reference align.")
            next_steps = ["Check which domain the aligned region belongs to before drawing conclusions."]
        elif z > Z_CHANCE:
            rule, cat = "N1", INSUFFICIENT
            summary = (f"No reliable similarity band, and the score (z = {z:.1f}) is between the shuffled-sequence "
                       f"range ({Z_CHANCE:g}) and the strong-similarity threshold ({Z_STRONG:g}).")
            next_steps = ["Use a more sensitive homology search before deciding on lab work."]
        else:
            rule, cat = "N2", RED
            summary = ("No convincing similarity to any characterised PET-degrading enzyme: identity and coverage are "
                       f"below every similarity band and the score is within the shuffled-sequence range (z = {z:.1f}). "
                       "This does not show the protein is PET-inactive; it means the sequence evidence does not "
                       "support prioritising it.")
            next_steps = ["No follow-up suggested on sequence grounds. Only a laboratory assay could establish "
                          "activity (or its absence)."]
    return _result(cat, rule, summary, reasons, limitations, next_steps, top, motifs, repeat, False)


def _result(cat, rule, summary, reasons, limitations, next_steps, top, motifs, repeat, known) -> dict:
    metrics = None
    if top is not None:
        metrics = {"identity": round(top.identity, 4), "query_coverage": round(top.query_coverage, 4),
                   "target_coverage": round(top.target_coverage, 4),
                   "min_coverage": round(min(top.query_coverage, top.target_coverage), 4),
                   "shuffled_z": round(top.shuffled_z, 1), "band": top.interpretation,
                   "closest_reference": top.protein_name, "closest_reference_id": top.protein_id}
    return {
        "category": cat, "label": LABELS[cat], "rule": rule,
        "rule_condition": _RULE[rule]["condition"] if rule in _RULE else None,
        "known_reference": known, "summary": summary, "reasons": reasons,
        "limitations": limitations, "next_steps": next_steps,
        "motif_count": motifs, "tandem_repeat_period": repeat, "metrics": metrics,
        "rules_version": RULES_VERSION,
        "disclaimer": "Sequence-based evidence assessment, not a validated prediction of PET-degrading activity.",
    }


# ------------------------------------------------------------------ calibration (reproducible)

F_CALIBRATION = C.MATCHING / "evidence_calibration.csv"
F_CALIBRATION_SUMMARY = C.MATCHING / "evidence_calibration_summary.json"


def calibration_summary() -> Optional[dict]:
    return json.loads(F_CALIBRATION_SUMMARY.read_text()) if F_CALIBRATION_SUMMARY.exists() else None


def calibrate(seed: int = 42):
    """Shuffled-query null vs leave-one-out true relatives; writes the per-query table and a summary."""
    import random

    import pandas as pd

    from .preprocess import load_proteins
    from .sequence_matching import SequenceMatcher

    proteins = load_proteins()
    m = SequenceMatcher(proteins)
    card = proteins.set_index("protein_id")
    rng = random.Random(seed)
    rows = []
    for i, seq in enumerate(m.ref.sequence):
        pid = int(m.ref.protein_id[i])
        s = list(seq)
        rng.shuffle(s)
        for kind, q, excl in (("shuffled_null", "".join(s), ()), ("leave_one_out", seq, (pid,))):
            _, qseq, hits = m.search(q, top_n=1, n_shuffles=N_SHUFFLES, seed=SHUFFLE_SEED, exclude_ids=excl)
            h = hits[0]
            ref = card.loc[h.protein_id].to_dict()
            a = assess(h, ref, qseq)
            rows.append({"kind": kind, "query_protein_id": pid, "top_hit": h.protein_name, "identity": h.identity,
                         "query_coverage": h.query_coverage, "target_coverage": h.target_coverage,
                         "shuffled_z": h.shuffled_z, "band": h.interpretation,
                         "category": a["category"], "rule": a["rule"]})
    df = pd.DataFrame(rows)
    C.MATCHING.mkdir(parents=True, exist_ok=True)
    df.to_csv(F_CALIBRATION, index=False)
    summary = {"n_per_set": int(len(df) // 2), "seed": seed, "n_shuffles": N_SHUFFLES}
    for kind, g in df.groupby("kind"):
        summary[kind] = {
            "z_quantiles": {q: round(float(g.shuffled_z.quantile(float(q))), 1) for q in ("0.5", "0.9", "0.99")},
            "z_min": round(float(g.shuffled_z.min()), 1), "z_max": round(float(g.shuffled_z.max()), 1),
            "categories": {k: int(v) for k, v in g.category.value_counts().items()},
        }
    tw = df[(df.kind == "leave_one_out") & (df.band == TWILIGHT_BAND)]
    summary["leave_one_out"]["twilight_band_z_min"] = round(float(tw.shuffled_z.min()), 1) if len(tw) else None
    F_CALIBRATION_SUMMARY.write_text(json.dumps(summary, indent=2))
    return df, summary


if __name__ == "__main__":  # python -m pet_explorer.evidence
    _, s = calibrate()
    print(json.dumps(s, indent=2))
