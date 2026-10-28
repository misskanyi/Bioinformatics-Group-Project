"""Display layout for the similarity network (presentation only).

The cached spring layout (network/ssn_layout.csv) lays out the whole graph at
once, so isolated proteins push the large component into a small central
blob. Here each connected component of the default network is laid out on its
own and the components are packed: largest first, small groups in rows,
singletons in a grid underneath. Positions carry no meaning beyond grouping.
"""

from functools import lru_cache

import networkx as nx
import numpy as np

from pet_explorer import config as C

from . import store


@lru_cache
def packed_layout() -> dict:
    p = store.proteins()
    pr = store.pairs()
    e = pr[(pr.identity >= C.EDGE_MIN_IDENTITY) & (pr.min_coverage >= C.EDGE_MIN_COVERAGE)]
    g = nx.Graph()
    g.add_nodes_from(p.protein_id)
    g.add_weighted_edges_from(zip(e.protein_id_a, e.protein_id_b, e.identity))
    comps = sorted(nx.connected_components(g), key=lambda c: (-len(c), min(c)))

    pos = {}
    big = [c for c in comps if len(c) > 1]
    singles = [next(iter(c)) for c in comps if len(c) == 1]

    # giant component: unit-ish disc of radius ~1
    x_cursor, y_row, row_h = 0.0, 0.0, 0.0
    for i, comp in enumerate(big):
        sub = g.subgraph(comp)
        n = len(comp)
        if n > 30:  # spreads a dense component evenly by graph distance
            xy = nx.kamada_kawai_layout(sub)
        else:
            xy = nx.spring_layout(sub, seed=7, k=1.6 / np.sqrt(n), iterations=150, weight="weight")
        arr = np.array(list(xy.values()))
        arr -= arr.mean(axis=0)
        span = np.percentile(np.linalg.norm(arr, axis=1), 98) or 1.0
        radius = 1.0 if i == 0 else max(0.05, 0.16 * np.sqrt(n / 10))
        arr = arr / span * radius
        if i == 0:
            offset = np.array([0.0, 0.0])
            x_cursor, y_row = 1.25, -1.0
        else:
            if x_cursor + 2 * radius > 2.1:
                x_cursor, y_row = 1.25, y_row + row_h + 0.08
                row_h = 0.0
            offset = np.array([x_cursor + radius, y_row + radius])
            x_cursor += 2 * radius + 0.08
            row_h = max(row_h, 2 * radius)
        for node, (x, y) in zip(xy.keys(), arr + offset):
            pos[node] = (float(x), float(y))

    # singletons: grid below everything
    top = 1.3
    cols = 20
    for j, node in enumerate(sorted(singles)):
        pos[node] = (-1.0 + (j % cols) * 0.1, top + (j // cols) * 0.1)
    return pos
