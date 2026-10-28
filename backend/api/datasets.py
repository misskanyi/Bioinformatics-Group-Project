"""Dataset Intelligence: provenance, quality metrics, limitations, downloads."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..services import store

router = APIRouter()

LIMITATIONS = [
    "No usable PET-inactive sequences exist in the provided data (4 tested-inactive proteins, 1 with high "
    "confidence), so a PET-active vs PET-inactive classifier cannot be trained or validated.",
    "Sequence similarity to a characterised enzyme is not evidence of PET activity; it only prioritises "
    "candidates for experimental testing.",
    "PAZy has no organism field. Organisms come from identical or overlapping sequences in PlasticDB, the "
    "PlasticDB degraders list and UniProt; the rest are reported as unknown.",
    "Assay conditions, units and detection methods differ between papers, so activity values are never "
    "pooled across studies and no temperature optimum is claimed.",
    "Literature coverage is uneven: one 2025 screening paper contributes a large share of the G1b proteins.",
    "Cluster G2 and G5 are heterogeneous remainder groups (mean within-group identity < 25%), not families.",
]


@router.get("/datasets")
def datasets():
    p = store.proteins()
    q = store.quality_summary()
    loo = store.leave_one_out()
    dois = p.dois.str.split("; ").explode().value_counts()
    a = store.temperature_assays()
    o = store.organisms()
    metric = dict(zip(q.metric, q.value))
    pipeline = [
        {"stage": "Raw data", "detail": "Six downloads: PAZy sequences (CSV + FASTA), PAZy polymer assays (JSON), "
                                        "PlasticDB FASTA, PlasticDB degraders list, UniProt FASTA.",
         "count": f"{metric.get('Total assay records (all substrates)', '?')} assays"},
        {"stage": "Quality control", "detail": "Assays classified POS / NEG / unclear / excluded; proteins labelled; "
                                               "sequences re-checked against the raw CSV.",
         "count": f"{len(p)} usable PET-active proteins"},
        {"stage": "Sequence analysis", "detail": "All-vs-all Smith-Waterman alignments (BLOSUM62) plus composition "
                                                 "and physicochemical features.",
         "count": f"{len(store.pairs()):,} protein pairs"},
        {"stage": "Clustering", "detail": "Average-linkage hierarchical clustering of alignment distances, chosen "
                                          "by silhouette and bootstrap stability; network at 40% identity / 70% coverage.",
         "count": f"{p.cluster.nunique()} clusters, {p.subcluster.nunique()} subgroups"},
        {"stage": "Biological interpretation", "detail": "Reported temperatures, assay outcomes and documented "
                                                         "organisms attached to every protein with provenance.",
         "count": f"{len(a):,} assays, {int((o.organism_evidence != 'none').sum())} organisms linked"},
    ]
    return {
        "inventory": store.records(store.inventory()),
        "quality": store.records(q),
        "qc_checks": store.records(store.qc_checks()),
        "pipeline": pipeline,
        "coverage": {
            "proteins": len(p),
            "with_organism": int((o.organism_evidence != "none").sum()),
            "with_temperature": int((store.temperature_summary().n_temperatures_tested > 0).sum()),
            "with_ph": int(a.groupby("protein_id").ph.apply(lambda s: s.notna().any()).sum()),
            "in_standardised_screen": int(p.in_standardised_screen.sum()),
            "with_plasticdb_record": int(p.plasticdb_ids.notna().sum()),
            "duplicate_sequences": int(len(p) - p.sequence.nunique()),
        },
        "leave_one_out": {
            "description": "Each reference protein queried against the other 297; band of its nearest neighbour.",
            "bands": {k: int(v) for k, v in loo.band.value_counts().items()},
            "median_identity": round(float(loo["id"].median()), 3),
        },
        "references": [{"doi": d, "n_proteins": int(n)} for d, n in dois.items()],
        "limitations": LIMITATIONS,
        "downloads": [{"key": k, "file": path.name, "description": desc, "available": path.exists()}
                      for k, (path, desc) in store.DOWNLOADS.items()],
    }


@router.get("/downloads/{key}")
def download(key: str):
    if key not in store.DOWNLOADS:
        raise HTTPException(404, "Unknown download.")
    path, _ = store.DOWNLOADS[key]
    if not path.exists():
        raise HTTPException(404, f"{path.name} has not been generated yet.")
    return FileResponse(path, filename=path.name)
