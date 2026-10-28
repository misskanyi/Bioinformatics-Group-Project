"""Protein Networks: sequence-similarity network and clustering views."""

import json

import networkx as nx
import numpy as np
import pandas as pd
from fastapi import APIRouter, Query

from pet_explorer import config as C
from pet_explorer.plots import group_key

from ..services import layout, store

router = APIRouter()


@router.get("/network")
def network(min_identity: float = Query(C.EDGE_MIN_IDENTITY, ge=0.3, le=1.0),
            min_coverage: float = Query(C.EDGE_MIN_COVERAGE, ge=0.5, le=1.0)):
    """Edges are re-filtered from the full all-vs-all alignment table, so any
    threshold in range uses the same alignments as the exported network."""
    p = store.proteins()
    pr = store.pairs()
    e = pr[(pr.identity >= min_identity) & (pr.min_coverage >= min_coverage)]
    g = nx.Graph()
    g.add_nodes_from(p.protein_id)
    g.add_edges_from(zip(e.protein_id_a, e.protein_id_b))
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    comp_of = {n: i for i, c in enumerate(comps) for n in c}
    pos = layout.packed_layout()
    o = store.organisms().set_index("protein_id")
    t = store.temperature_summary().set_index("protein_id")
    nodes = [{
        "id": int(r.protein_id), "name": r.protein_name, "cluster": r.cluster, "subcluster": r.subcluster,
        "length": int(r.sequence_length), "degree": int(g.degree(r.protein_id)),
        "component": comp_of[r.protein_id],
        "x": pos[r.protein_id][0], "y": pos[r.protein_id][1],
        "organism": o.organism.get(r.protein_id), "organism_evidence": o.organism_evidence.get(r.protein_id),
        "n_temperatures": int(t.n_temperatures_tested.get(r.protein_id, 0)),
    } for r in p.itertuples()]
    edges = [[int(a), int(b), round(float(i), 3), round(float(c), 3)]
             for a, b, i, c in zip(e.protein_id_a, e.protein_id_b, e.identity, e.min_coverage)]
    sizes = [len(c) for c in comps]
    return {
        "threshold": {"min_identity": min_identity, "min_coverage": min_coverage},
        "nodes": nodes,
        "edges": edges,
        "edge_fields": ["source", "target", "identity", "min_coverage"],
        "stats": {"edges": len(edges), "components": len(comps), "largest_component": sizes[0],
                  "isolated": sizes.count(1)},
        "layout_note": "Positions come from a fixed layout of the default network (identity >= 40%, "
                       "coverage >= 70%): each connected component is laid out separately, isolated proteins "
                       "sit in the grid below. Positions do not move when the threshold changes and distance "
                       "on screen is not a measured quantity.",
    }


@router.get("/network/sensitivity")
def sensitivity():
    return store.records(store.sensitivity())


@router.get("/clustering")
def clustering():
    a = store.assignments()
    f = store.features()
    sel = json.loads((C.CLUSTERING / "clustering_selection.json").read_text())
    order = sorted(a.subcluster.unique(), key=group_key)

    points = [{"id": int(r.protein_id), "name": r.protein_name, "subcluster": r.subcluster,
               "pca": [round(r.pca1, 4), round(r.pca2, 4)], "mds": [round(r.mds1, 5), round(r.mds2, 5)]}
              for r in a.itertuples()]

    aa_cols = [c for c in f.columns if c.startswith("aa_")]
    comp = f[["protein_id"] + aa_cols].merge(a[["protein_id", "subcluster"]], on="protein_id")
    overall = comp[aa_cols].mean()
    by = comp.groupby("subcluster")[aa_cols].mean()
    composition = [{"aa": c[3:], "all": round(float(overall[c]), 2),
                    **{s: round(float(by.loc[s, c]), 2) for s in order}} for c in aa_cols]

    # identity heatmap, proteins ordered by subcluster then by first MDS axis
    ordered = a.assign(k=a.subcluster.map(lambda s: order.index(s))).sort_values(["k", "mds1"])
    ids = ordered.protein_id.tolist()
    idx = {pid: i for i, pid in enumerate(ids)}
    m = np.full((len(ids), len(ids)), 100, dtype=np.int16)
    pr = store.pairs()
    ia = pr.protein_id_a.map(idx).to_numpy()
    ib = pr.protein_id_b.map(idx).to_numpy()
    v = np.rint(pr.identity.to_numpy() * 100).astype(np.int16)
    m[ia, ib] = v
    m[ib, ia] = v

    return {
        "subclusters": order,
        "points": points,
        "pca_variance": sel["pca_variance_explained"],
        "mds_variance": sel["mds_variance_explained"],
        "composition": composition,
        "summary": store.records(store.cluster_summary()),
        "selection": sel,
        "heatmap": {"ids": ids, "subclusters": ordered.subcluster.tolist(),
                    "names": ordered.protein_name.tolist(), "matrix": m.tolist()},
        "method_comparison": store.records(pd.read_csv(C.CLUSTERING / "method_comparison.csv")),
    }
