"""Landing-page statistics and protein lookup."""

from fastapi import APIRouter, HTTPException

from ..services import store

router = APIRouter()


def _dois(p):
    return p.dois.str.split("; ").explode().dropna()


@router.get("/overview")
def overview():
    p = store.proteins()
    o = store.organisms()
    t = store.temperature_summary()
    a = store.temperature_assays()
    s = store.sensitivity()
    default = s[(s.min_identity.round(2) == 0.40) & (s.min_coverage.round(2) == 0.70)].iloc[0]
    with_org = int((o.organism_evidence != store.UNKNOWN_EVIDENCE).sum())
    with_temp = int((t.n_temperatures_tested > 0).sum())
    series = int((t.optimum_status_category == "comparable series (>=3 temperatures)").sum())
    sizes = p.subcluster.value_counts()
    largest = sizes.index[0]
    evidence_counts = o.organism_evidence.value_counts().to_dict()
    detected = int((a.degradation_detected == "detected").sum())
    n = len(p)

    stats = {
        "proteins": n,
        "publications": int(_dois(p).nunique()),
        "clusters": int(p.cluster.nunique()),
        "subclusters": int(p.subcluster.nunique()),
        "proteins_with_organism": with_org,
        "organism_names": int(o.loc[o.organism_evidence != store.UNKNOWN_EVIDENCE, "organism"]
                              .str.split("; ").explode().nunique()),
        "proteins_with_temperature": with_temp,
        "pet_assays": int(len(a)),
        "assays_detected": detected,
        "network_edges": int(default.edges),
        "network_components": int(default.components),
        "network_isolated": int(default.isolated_proteins),
    }
    insights = [
        {"label": "Temperature records",
         "value": f"{with_temp}/{n}",
         "detail": f"proteins have at least one reported assay temperature; {series} have a comparable "
                   f"series of three or more temperatures from one protocol."},
        {"label": "Organism annotations",
         "value": f"{with_org}/{n}",
         "detail": f"proteins have a source organism from database records "
                   f"({evidence_counts.get('exact_sequence', 0)} identical sequence, "
                   f"{evidence_counts.get('contained_sequence', 0)} precursor/mature-form overlap). "
                   f"{n - with_org} remain unknown."},
        {"label": "Sequence groups",
         "value": str(stats["clusters"]),
         "detail": f"clusters from average-linkage clustering of alignment distances; the largest "
                   f"subgroup {largest} holds {int(sizes.iloc[0])} proteins ({100 * sizes.iloc[0] / n:.0f}%)."},
        {"label": "Assay outcomes",
         "value": f"{100 * detected / len(a):.0f}%",
         "detail": f"of {len(a):,} PET assays on these proteins reported detectable breakdown products; "
                   f"the rest were negative, unclear or excluded under the reported conditions."},
        {"label": "Similarity network",
         "value": f"{int(default.edges):,}",
         "detail": f"edges at >= 40% identity and >= 70% coverage; {int(default.components)} connected "
                   f"components, {int(default.isolated_proteins)} isolated proteins."},
    ]
    return {"stats": stats, "insights": insights,
            "cluster_sizes": [{"subcluster": k, "n": int(v)} for k, v in sizes.items()]}


@router.get("/proteins")
def protein_index():
    p = store.proteins()
    o = store.organisms().set_index("protein_id")
    return [{"protein_id": int(r.protein_id), "protein_name": r.protein_name, "cluster": r.cluster,
             "subcluster": r.subcluster, "sequence_length": int(r.sequence_length),
             "organism": o.organism.get(r.protein_id), "organism_evidence": o.organism_evidence.get(r.protein_id)}
            for r in p.itertuples()]


@router.get("/proteins/{protein_id}")
def protein_detail(protein_id: int):
    p = store.proteins()
    if protein_id not in set(p.protein_id):
        raise HTTPException(404, f"Protein {protein_id} is not in the PET-active reference set.")
    card = store.protein_card(protein_id)
    card["sequence"] = p.loc[p.protein_id == protein_id, "sequence"].iloc[0]
    org = store.organism_row(protein_id)
    card["closest_relative_with_known_organism"] = org.get("closest_relative_with_known_organism")
    card["closest_relative_note"] = org.get("closest_relative_note")
    links = store.organism_links()
    card["organism_links"] = store.records(links[links.protein_id == protein_id]) if len(links) else []
    pr = store.pairs()
    nb = pr[(pr.protein_id_a == protein_id) | (pr.protein_id_b == protein_id)].nlargest(5, "normalised_score")
    names = dict(zip(p.protein_id, p.protein_name))
    card["nearest_references"] = [
        {"protein_id": int(other), "protein_name": names[other], "identity": float(r.identity),
         "min_coverage": float(r.min_coverage)}
        for r in nb.itertuples()
        for other in [r.protein_id_b if r.protein_id_a == protein_id else r.protein_id_a]]
    return card
