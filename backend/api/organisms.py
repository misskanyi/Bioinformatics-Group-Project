"""Organism Explorer: documented source organisms, with evidence level.

An organism is linked to a protein only through records produced by
pet_explorer.organisms (identical or overlapping database sequences, or PAZy
curation text). Sequence similarity alone never assigns an organism; the
closest relative with a known organism is returned separately as context.
"""

from fastapi import APIRouter

from ..services import store

router = APIRouter()

EVIDENCE_LABELS = {
    "exact_sequence": "Directly documented - identical database sequence",
    "contained_sequence": "Database match - precursor / mature form of the same sequence",
    "pazy_curation_text": "Reported in literature text - not sequence-verified",
    "none": "Unknown - insufficient evidence",
}
RANK = list(EVIDENCE_LABELS)


def _vals(series):
    return sorted({v for v in series if v and v != "Not documented in provided files"})


@router.get("/organisms")
def organisms():
    o = store.organisms()
    links = store.organism_links()
    p = store.proteins().set_index("protein_id")
    known = o[o.organism_evidence != store.UNKNOWN_EVIDENCE]

    by_org = {}
    for r in known.itertuples():
        for name in store.split(r.organism):
            entry = by_org.setdefault(name, {"proteins": []})
            entry["proteins"].append({
                "protein_id": int(r.protein_id), "protein_name": r.protein_name,
                "subcluster": p.subcluster.get(r.protein_id), "evidence": r.organism_evidence,
                "confidence": r.confidence, "sources_disagree": bool(r.sources_disagree),
            })

    cards = []
    for name, entry in by_org.items():
        lk = links[links.organism == name] if len(links) else links
        best = min((x["evidence"] for x in entry["proteins"]), key=RANK.index)
        cards.append({
            "organism": name,
            "genus": name.split()[0],
            "uncultured": any(w in name.lower() for w in ("uncultured", "metagenom", "bacterium")),
            "taxonomy_ids": _vals(lk.taxonomy_id) if len(lk) else [],
            "sources": _vals(lk.source) if len(lk) else [],
            "accessions": _vals(lk.accession)[:8] if len(lk) else [],
            "isolation_environment": _vals(lk.isolation_environment) if len(lk) else [],
            "isolation_sample_type": _vals(lk.isolation_sample_type) if len(lk) else [],
            "isolation_location": _vals(lk.isolation_location) if len(lk) else [],
            "best_evidence": best,
            "n_proteins": len(entry["proteins"]),
            "proteins": sorted(entry["proteins"], key=lambda x: x["protein_name"]),
        })
    cards.sort(key=lambda c: (-c["n_proteins"], c["organism"]))

    unknown = o[o.organism_evidence == store.UNKNOWN_EVIDENCE]
    return {
        "organisms": cards,
        "evidence_labels": EVIDENCE_LABELS,
        "evidence_counts": {k: int((o.organism_evidence == k).sum()) for k in RANK},
        "n_proteins": len(o),
        "unknown": [{"protein_id": int(r.protein_id), "protein_name": r.protein_name,
                     "subcluster": p.subcluster.get(r.protein_id),
                     "closest_relative": r.closest_relative_with_known_organism
                     if isinstance(r.closest_relative_with_known_organism, str) else None}
                    for r in unknown.itertuples()],
        "context_note": "Closest relatives are shown for context only; a similar sequence does NOT "
                        "establish the producing organism.",
    }
