"""Candidate shortlist for laboratory testing, from sequence evidence only.

    .venv/bin/python -m pet_explorer.shortlist

Input: the sequences that `pet_explorer.curation` marked `eligible_for_ranking`
(outputs/curation/candidate_eligibility.csv): annotation-only records from
PlasticDB / degraders_list with no PET testing evidence identified in any of our
sources. Every one of them is searched against the 298 curated PET-active
reference proteins with exactly the search and rules the web app uses
(Smith-Waterman / BLOSUM62, 25 composition-preserving shuffles, seed 0,
`evidence.assess`). Nothing here uses the supervised 60 °C model, which did not
beat its shuffled-label null.

Priority tiers (sequence evidence only, never a probability of activity):
  1  strong homolog      green, clear-homolog band (40-90% identity, >= 70% coverage
                         of both, z >= 15, G-x-S-x-G present, well-supported reference)
  2  near-identical      >= 90% identity over >= 80% of both sequences to a characterised
                         enzyme: most likely to behave like it, least novel
  3  possible            yellow: motif missing, weaker reference, partial, remote or
                         domain-level similarity
  4  not prioritised     insufficient evidence (signals disagree, fragment, short match)
  5  not prioritised     red: no convincing similarity (NOT evidence of inactivity)
Within a tier, rows are ordered by the length-normalised alignment score of the
top hit; this orders the list for reading and is not a probability.

Outputs (outputs/explorer/shortlist/):
  candidate_shortlist.csv   one row per eligible candidate
  shortlist_summary.json    counts per tier / category / rule
"""

import json
import re

import pandas as pd

from . import config as C
from . import evidence as E
from .features import GXSXG
from .preprocess import load_proteins
from .sequence_matching import SequenceInputError, SequenceMatcher, parse_query

SHORTLIST = C.EXPLORER / "shortlist"
F_SHORTLIST = SHORTLIST / "candidate_shortlist.csv"
F_SUMMARY = SHORTLIST / "shortlist_summary.json"
F_ELIGIBILITY = C.ROOT / "outputs" / "curation" / "candidate_eligibility.csv"
F_MASTER = C.ROOT / "outputs" / "curation" / "proteins_master.csv"

NEAR_IDENTICAL = C.MATCH_BANDS[0][2]
# A candidate this close to a reference is treated as a second record of the same enzyme.
SAME_ENZYME_IDENTITY, SAME_ENZYME_REF_COVERAGE = 0.99, 0.98
TIERS = {
    1: "Priority: strong homolog of a characterised PET hydrolase",
    2: "Confirmatory: near-identical to a characterised PET hydrolase",
    3: "Possible: weaker or partial sequence evidence",
    4: "Not prioritised: insufficient sequence evidence",
    5: "Not prioritised: no convincing similarity",
}
LIMITATIONS = (
    "Sequence evidence only, not a validated prediction of PET-degrading activity. "
    "Evidence belongs to the matched reference enzyme, not to this candidate. "
    "'Eligible' means no PET testing evidence was found in the project's sources; check the cited literature "
    "before ordering genes. Activity depends on substrate form, temperature and pH, and single active-site "
    "substitutions can abolish it."
)


def tier(category, band, rule):
    if rule == "K" or (category == E.GREEN and band == NEAR_IDENTICAL):
        return 2
    if category == E.GREEN:
        return 1
    if category == E.YELLOW:
        return 2 if band == NEAR_IDENTICAL else 3
    if category == E.INSUFFICIENT:
        return 4
    return 5


def reason_text(t, a):
    m = a["metrics"]
    if t == 1:
        return (f"Clear homolog of {m['closest_reference']} ({100 * m['identity']:.0f}% identity, "
                f"{100 * m['min_coverage']:.0f}%+ coverage of both, z = {m['shuffled_z']:.0f}) with the catalytic "
                "motif and a well-supported reference: strongest sequence case for a new PET hydrolase.")
    if t == 2:
        if m["identity"] >= SAME_ENZYME_IDENTITY and m["target_coverage"] >= SAME_ENZYME_REF_COVERAGE:
            return (f"Probably the same enzyme as {m['closest_reference']} under another record "
                    f"({100 * m['identity']:.1f}% identity over {100 * m['target_coverage']:.0f}% of the reference; "
                    "precursor, tagged or single-variant form). Treat as already characterised.")
        return (f"Near-identical to {m['closest_reference']} ({100 * m['identity']:.0f}% identity): likely to behave "
                "like a known enzyme; testing would mainly confirm, not discover.")
    if t == 3:
        return f"Possible candidate (rule {a['rule']}): {a['rule_condition']}."
    if t == 4:
        return f"Not prioritised (rule {a['rule']}): {a['rule_condition']}."
    return "Not prioritised: no convincing similarity to any characterised PET hydrolase (not evidence of inactivity)."


def plasticdb_annotations():
    """PlasticDB id -> plastics field of the FASTA header (context only, never used for ranking)."""
    out = {}
    for line in open(C.F_PLASTICDB):
        if line.startswith(">"):
            parts = line[1:].strip().split("|")
            if len(parts) >= 4:
                out[parts[0]] = parts[3].replace("_", ", ")
    return out


def candidates():
    elig = pd.read_csv(F_ELIGIBILITY)
    master = pd.read_csv(F_MASTER)
    c = elig[elig.eligible_for_ranking].merge(
        master[["sequence_sha1", "sequence", "accessions", "organism", "dois", "source_record_ids"]],
        on="sequence_sha1", how="left")
    return c.sort_values("sequence_sha1").reset_index(drop=True)


def build():
    proteins = load_proteins()
    cards = proteins.set_index("protein_id")
    matcher = SequenceMatcher(proteins)
    pdb = plasticdb_annotations()
    rows = []
    for r in candidates().itertuples():
        pdb_ids = re.findall(r"PlasticDB:(\d+)", str(r.source_record_ids))
        base = {
            "candidate_id": r.sequence_sha1[:12], "sequence_sha1": r.sequence_sha1, "name": r.primary_name,
            "accessions": r.accessions, "organism": r.organism, "length": int(r.sequence_length),
            "source_records": r.source_record_ids, "source_dois": r.dois,
            "plasticdb_plastics_annotation": "; ".join(sorted({pdb[i] for i in pdb_ids if i in pdb})) or None,
        }
        try:
            _, seq = parse_query(r.sequence)
        except SequenceInputError as exc:
            rows.append({**base, "evidence_category": "invalid", "priority_tier": None,
                         "priority_label": "Not assessed: invalid sequence", "prioritisation_reason": str(exc),
                         "limitations": LIMITATIONS})
            continue
        _, _, hits = matcher.search(seq, top_n=1, n_shuffles=E.N_SHUFFLES, seed=E.SHUFFLE_SEED)
        h = hits[0]
        ref = cards.loc[h.protein_id]
        a = E.assess(h, ref.to_dict(), seq)
        t = tier(a["category"], h.interpretation, a["rule"])
        motifs = sorted({m.group(1) for m in GXSXG.finditer(seq)})
        rows.append({
            **base,
            "closest_reference": h.protein_name, "closest_reference_id": h.protein_id,
            "identity": round(h.identity, 4), "candidate_coverage": round(h.query_coverage, 4),
            "reference_coverage": round(h.target_coverage, 4), "aligned_columns": h.aligned_columns,
            "normalised_score": round(h.normalised_score, 4), "shuffled_z": round(h.shuffled_z, 1),
            "similarity_band": h.interpretation,
            "gxsxg_count": a["motif_count"], "gxsxg_variants": "; ".join(motifs) or None,
            "reference_pet_label": ref.pet_label, "reference_label_confidence": ref.label_confidence,
            "reference_pet_assays": int(ref.n_pet_assays), "reference_positive_assays": int(ref.n_positive_assays),
            "reference_publications": int(ref.n_publications),
            "evidence_category": a["category"], "evidence_label": a["label"], "rule": a["rule"],
            "priority_tier": t, "priority_label": TIERS[t], "prioritisation_reason": reason_text(t, a),
            "limitations": LIMITATIONS,
        })
    df = pd.DataFrame(rows)
    df["_t"] = df.priority_tier.fillna(99)
    df = df.sort_values(["_t", "normalised_score", "sequence_sha1"], ascending=[True, False, True],
                        na_position="last").drop(columns="_t").reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def summarise(df):
    return {
        "n_candidates": int(len(df)),
        "rules_version": E.RULES_VERSION, "n_shuffles": E.N_SHUFFLES, "shuffle_seed": E.SHUFFLE_SEED,
        "by_tier": {TIERS.get(int(k), str(k)): int(v)
                    for k, v in df.priority_tier.dropna().astype(int).value_counts().sort_index().items()},
        "invalid_sequences": int((df.evidence_category == "invalid").sum()),
        "by_category": {k: int(v) for k, v in df.evidence_category.value_counts().items()},
        "by_rule": {k: int(v) for k, v in df.rule.dropna().value_counts().items()},
        "candidates_citing_2025_screen_doi": int(df.source_dois.fillna("").str.contains("5c03460").sum()),
        "probably_same_enzyme_as_a_reference": int(df.prioritisation_reason.fillna("")
                                                   .str.startswith("Probably the same enzyme").sum()),
        "note": "Sequence-based evidence only; not a validated prediction of PET-degrading activity.",
    }


def run():
    SHORTLIST.mkdir(parents=True, exist_ok=True)
    df = build()
    df.to_csv(F_SHORTLIST, index=False)
    s = summarise(df)
    F_SUMMARY.write_text(json.dumps(s, indent=2))
    return df, s


if __name__ == "__main__":
    _, summary = run()
    print(json.dumps(summary, indent=2))
