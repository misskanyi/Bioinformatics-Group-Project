"""Sequence-similarity network (SSN) export for Cytoscape.

This is a SEQUENCE-SIMILARITY network: an edge means two proteins have
similar amino-acid sequences. It is NOT a protein-protein interaction network.

Edge rule: local-alignment identity >= 40% AND the alignment covers >= 70% of
BOTH sequences.
  * 40% identity over a long alignment is well above the ~25-35% "twilight
    zone" in which homology cannot be inferred from identity alone
    (Rost 1999, Protein Eng. 12:85-94), so edges indicate probable homology.
  * Requiring 70% coverage of both proteins stops a short shared fragment
    (e.g. a signal peptide or a single domain of a longer protein) from
    creating an edge.
A sensitivity table at other thresholds is written alongside.
"""

import networkx as nx
import pandas as pd

from . import config as C


def build_graph(nodes, pairs, min_identity=C.EDGE_MIN_IDENTITY, min_coverage=C.EDGE_MIN_COVERAGE):
    g = nx.Graph()
    for row in nodes.to_dict("records"):
        g.add_node(row["protein_id"], **row)
    e = pairs[(pairs.identity >= min_identity) & (pairs.min_coverage >= min_coverage)]
    for r in e.itertuples(index=False):
        g.add_edge(r.protein_id_a, r.protein_id_b, identity=r.identity, coverage_a=r.coverage_a,
                   coverage_b=r.coverage_b, min_coverage=r.min_coverage,
                   identity_shorter=r.identity_shorter, normalised_score=r.normalised_score)
    return g


def sensitivity(pairs, ids):
    rows = []
    for ident in (0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
        for cov in (0.5, 0.7, 0.8):
            e = pairs[(pairs.identity >= ident) & (pairs.min_coverage >= cov)]
            g = nx.Graph()
            g.add_nodes_from(ids)
            g.add_edges_from(zip(e.protein_id_a, e.protein_id_b))
            comps = sorted((len(c) for c in nx.connected_components(g)), reverse=True)
            rows.append({"min_identity": ident, "min_coverage": cov, "edges": len(e),
                         "components": len(comps), "isolated_proteins": comps.count(1),
                         "largest_component": comps[0]})
    return pd.DataFrame(rows)


def export_cytoscape(g, folder):
    """Write node and edge tables in Cytoscape's 'Import Network from File' layout."""
    nodes = pd.DataFrame([{"id": n, **{k: v for k, v in d.items() if k != "protein_id"}} for n, d in g.nodes(data=True)])
    nodes["degree"] = nodes.id.map(dict(g.degree()))
    edges = pd.DataFrame([{"source": a, "target": b, "interaction": "sequence_similarity", **d}
                          for a, b, d in g.edges(data=True)])
    nodes.to_csv(folder / "ssn_nodes.csv", index=False)
    edges.to_csv(folder / "ssn_edges.csv", index=False)
    return nodes, edges


def layout(g, seed=7):
    pos = nx.spring_layout(g, seed=seed, k=0.15, iterations=200)
    return pd.DataFrame([{"protein_id": n, "x": float(x), "y": float(y)} for n, (x, y) in pos.items()])
