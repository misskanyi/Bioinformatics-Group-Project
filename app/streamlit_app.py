"""PET Enzyme Explorer - Streamlit research dashboard.

Run from the project root:
    .venv/bin/streamlit run app/streamlit_app.py

The dashboard only READS cached results in outputs/explorer/ (produced by
`python -m pet_explorer.pipeline`); the only live computation is aligning a
user's query sequence against the 298 reference proteins.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pet_explorer import config as C  # noqa: E402
from pet_explorer.organisms import UNKNOWN  # noqa: E402
from pet_explorer.plots import SERIES, group_key  # noqa: E402
from pet_explorer.sequence_matching import SequenceInputError, SequenceMatcher, hits_to_frame  # noqa: E402

st.set_page_config(page_title="PET Enzyme Explorer", page_icon="🧬", layout="wide")

RESEARCH_QUESTION = (
    "Do experimentally verified PET-hydrolysing enzymes form distinct groups based on their amino-acid "
    "sequence features, and do these groups relate to the temperatures at which PET degradation was observed?")
HYPOTHESES = [
    "H1 - Most verified PET-active enzymes belong to a small number of sequence-similarity groups that share "
    "the serine-hydrolase G-x-S-x-G catalytic motif.",
    "H2 - Sequence groups differ in the temperatures at which PET degradation has been detected.",
]
SIMILARITY_WARNING = (
    "**Sequence similarity is a computational prediction, not experimental evidence.** "
    "A close match to an experimentally characterised PET-active enzyme makes your protein a *promising candidate* "
    "for PET degradation. It does not prove that your protein degrades PET: single amino-acid changes can abolish "
    "or create activity, and activity also depends on temperature, pH and the PET material. "
    "Only a laboratory assay can confirm PET degradation.")


# --------------------------------------------------------------------------- data
def _need(path):
    if not path.exists():
        st.error(f"Missing `{path.relative_to(ROOT)}`. Run `.venv/bin/python -m pet_explorer.pipeline` first.")
        st.stop()
    return path


@st.cache_data
def load(rel):
    return pd.read_csv(_need(C.EXPLORER / rel))


@st.cache_data
def load_feasibility(rel):
    return pd.read_csv(_need(C.FEASIBILITY / rel))


@st.cache_resource
def matcher():
    return SequenceMatcher(pd.read_csv(_need(C.F_PROTEINS)))


def proteins():
    return pd.read_csv(_need(C.F_PROTEINS))


def color_map(labels):
    return {g: SERIES[i % len(SERIES)] for i, g in enumerate(sorted(set(labels), key=group_key))}


def doi_links(dois):
    return " · ".join(f"[{d}](https://doi.org/{d})" for d in str(dois).split("; ") if d and d != "nan")


def protein_info():
    p = proteins()
    a = load("clustering/cluster_assignments.csv")[["protein_id", "cluster", "subcluster", "identity_group_70"]]
    o = load("organisms/protein_organisms.csv")
    t = load("temperature/protein_temperature_summary.csv")
    return (p.merge(a, on="protein_id")
            .merge(o.drop(columns="protein_name"), on="protein_id", how="left")
            .merge(t.drop(columns=["protein_name", "cluster", "subcluster", "n_pet_assays"]), on="protein_id", how="left")
            .set_index("protein_id"))


# --------------------------------------------------------------------------- page 1
def page_search():
    st.title("🔎 Protein Search")
    st.caption("Compare a protein sequence with 298 experimentally verified PET-active enzymes (PAZy).")
    st.warning(SIMILARITY_WARNING)

    p = proteins()
    examples = {"(type or paste your own)": "", **{f"Example: {n} (PAZy {i})": s for i, n, s in
                                                     zip(p.protein_id, p.protein_name, p.sequence) if n in ("ISPETase", "LCC", "TfCut2")}}
    choice = st.selectbox("Example sequences", list(examples))
    text = st.text_area("Protein sequence (plain text or FASTA; 20 standard amino acids only)",
                        value=examples[choice], height=160, placeholder=">my_protein\nMNFPRASRLMQAAVLGGL...")
    if st.button("Analyse", type="primary"):
        try:
            with st.spinner("Aligning against 298 reference proteins..."):
                st.session_state["search"] = matcher().search(text, top_n=5)
        except SequenceInputError as e:
            st.session_state.pop("search", None)
            st.error(f"Invalid input: {e}")
    if "search" not in st.session_state:
        st.info("Method: Smith-Waterman local alignment (BLOSUM62, gap open -11 / extend -1). Matches are ranked by a "
                "length-normalised score (raw score / √(self-score of query × self-score of match)), so long proteins "
                "are not favoured just for being long.")
        return

    header, query, hits = st.session_state["search"]
    info = protein_info()
    st.subheader(f"Top 5 matches for `{header}` ({len(query)} aa)")
    df = hits_to_frame(hits, p)
    df["cluster"] = df.protein_id.map(info.subcluster)
    df["organism"] = df.protein_id.map(info.organism)
    st.dataframe(df.drop(columns=["raw_score"]), hide_index=True, use_container_width=True, column_config={
        "identity_pct": st.column_config.NumberColumn("Identity %", help="Identical residues / aligned columns"),
        "query_coverage_pct": st.column_config.NumberColumn("Query cov. %", help="Share of YOUR sequence inside the alignment"),
        "target_coverage_pct": st.column_config.NumberColumn("Match cov. %", help="Share of the MATCHED protein inside the alignment"),
        "normalised_score": st.column_config.NumberColumn("Norm. score", help="1.0 = identical; used for ranking"),
        "shuffled_z": st.column_config.NumberColumn("z vs shuffled", help="How far the score lies above 25 shuffled copies of your sequence; > 10 is far beyond chance"),
        "pet_evidence": st.column_config.TextColumn("Experimental PET evidence (for the MATCH)", width="large"),
    })
    top = hits[0]
    if top.interpretation.startswith(("Near", "Clear")):
        st.success(f"**Computational prediction:** your sequence is a *{top.interpretation.lower()}* "
                   f"({top.protein_name}, {100 * top.identity:.0f}% identity over {100 * min(top.query_coverage, top.target_coverage):.0f}% "
                   f"coverage). It would fall in sequence group **{info.subcluster[top.protein_id]}**. "
                   "Treat it as a promising candidate for PET-degradation testing, not as a confirmed PET degrader.")
    else:
        st.info(f"**Computational prediction:** best match is in the '{top.interpretation}' range. "
                "Sequence similarity alone does not support a PET-degradation prediction for this protein.")

    st.divider()
    names = {f"#{i + 1} {h.protein_name} (PAZy {h.protein_id})": h for i, h in enumerate(hits)}
    h = names[st.selectbox("Inspect a match", list(names))]
    r = info.loc[h.protein_id]
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(f"**Alignment** - query residues {h.query_range[0]}-{h.query_range[1]}, "
                    f"match residues {h.target_range[0]}-{h.target_range[1]}, {h.aligned_columns} columns  \n"
                    "`|` identical · `.` substitution · `-` gap")
        st.code(h.alignment_text.replace("target", "match ").replace("query ", "yours "), language=None)
    with c2:
        st.markdown("**Experimentally established (from PAZy assays)**")
        st.markdown(f"- Label: **{r.pet_label}** ({r.label_confidence} confidence)\n"
                    f"- {r.n_positive_assays} of {r.n_pet_assays} PET assays detected degradation, {r.n_publications} publication(s)\n"
                    f"- Temperatures tested: {r.temperatures_tested_c if pd.notna(r.temperatures_tested_c) else 'none recorded'} °C\n"
                    f"- Temperatures with detected activity: {r.temperatures_with_activity_c if pd.notna(r.temperatures_with_activity_c) else '-'} °C\n"
                    f"- Temperature optimum: {r.temperature_optimum_status}\n"
                    f"- PET forms tested: {r.substrate_forms}")
        st.markdown("**Organism of the matched protein**")
        st.markdown(f"- {r.organism}" + (f" (NCBI Tax ID {r.taxonomy_id})" if isinstance(r.taxonomy_id, str) and r.taxonomy_id else "") +
                    f"\n- Evidence: {r.association_type}; confidence {r.confidence}\n"
                    f"- Sources: {r.evidence_sources or '-'}")
        if r.organism == UNKNOWN and r.closest_relative_with_known_organism:
            st.caption(f"Closest relative with known organism: {r.closest_relative_with_known_organism}. "
                       "Context only - this does not establish the producing organism.")
        st.markdown("**References:** " + doi_links(r.dois))


# --------------------------------------------------------------------------- page 2
def page_clusters():
    st.title("🧩 Protein Clusters")
    a = load("clustering/cluster_assignments.csv")
    feats = load("clustering/sequence_features.csv")
    summ = load("clustering/cluster_summary.csv")
    comp = load("clustering/method_comparison.csv")
    sub = load("clustering/g1_subgroup_comparison.csv")
    cmap = color_map(a.subcluster)

    c = st.columns(4)
    c[0].metric("Proteins clustered", len(a))
    c[1].metric("Clusters (level 1)", a.cluster.nunique())
    c[2].metric("Groups incl. G1 split", a.subcluster.nunique())
    c[3].metric("Pairwise alignments", f"{len(a) * (len(a) - 1) // 2:,}")

    st.markdown(
        "**Method.** Three unsupervised approaches were compared on the same proteins: hierarchical clustering "
        "(average linkage) on alignment distance, k-means on standardised composition/physicochemical features, and "
        "DBSCAN on alignment distance. The final configuration was chosen by a rule fixed in advance: stable "
        "(subsample ARI ≥ 0.9), ≤ 5% unassigned, mean within-cluster identity ≥ 40%, then best silhouette. "
        "→ **hierarchical clustering, 7 clusters**. G1 (263 proteins) was then re-clustered; a perfectly "
        "reproducible but *weakly separated* split (silhouette 0.16) gives **G1a / G1b**.")

    t1, t2, t3, t4, t5 = st.tabs(["Cluster map", "Cluster summaries", "Sequence characteristics",
                                  "Method evaluation", "Similarity network"])
    with t1:
        view = st.radio("Projection", ["Alignment distance (MDS)", "Sequence features (PCA)"], horizontal=True)
        x, y = ("mds1", "mds2") if view.startswith("Alignment") else ("pca1", "pca2")
        fig = px.scatter(a, x=x, y=y, color="subcluster", symbol="subcluster", hover_name="protein_name",
                         hover_data={"protein_id": True, "cluster": True, x: False, y: False},
                         color_discrete_map=cmap, category_orders={"subcluster": sorted(cmap, key=group_key)})
        fig.update_traces(marker=dict(size=8, line=dict(width=1, color="white")))
        fig.update_layout(height=520, legend_title_text="Group")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("MDS places proteins so that map distance approximates alignment distance. PCA uses only "
                   "composition/physicochemical features, which separate the families poorly (k-means on these "
                   "features agrees with the alignment clusters at ARI 0.08).")
        st.image(str(C.FIGURES / "f07_identity_heatmap.png"), caption="Pairwise identity heatmap", width=650)
    with t2:
        st.dataframe(summ, hide_index=True, use_container_width=True)
        kmers = load("clustering/cluster_specific_kmers.csv")
        st.markdown("**Cluster-specific 5-mers** (in ≥ 80% of the group, ≤ 20% of other proteins)")
        st.dataframe(kmers, hide_index=True)
        sizes = a.subcluster.value_counts().reindex(sorted(cmap, key=group_key))
        st.plotly_chart(px.bar(x=sizes.index, y=sizes.values, log_y=True, labels={"x": "Group", "y": "Proteins (log)"},
                               title="Cluster-size distribution", text=sizes.values,
                               color_discrete_sequence=[SERIES[0]]), use_container_width=True)
    with t3:
        fa = feats.merge(a[["protein_id", "subcluster"]], on="protein_id")
        st.plotly_chart(px.histogram(fa, x="length", nbins=40, color_discrete_sequence=[SERIES[0]],
                                     title="Sequence length (aa)"), use_container_width=True)
        aa = [f"aa_{x}" for x in C.STANDARD_AA]
        comp_mean = fa.groupby("subcluster")[aa].mean().reindex(sorted(cmap, key=group_key))
        z = (comp_mean - fa[aa].mean()) / fa[aa].std()
        st.plotly_chart(px.imshow(z.rename(columns=lambda c: c[-1]), color_continuous_scale="RdBu_r", zmin=-2, zmax=2,
                                  aspect="auto", title="Amino-acid composition by group (SD from overall mean)"),
                        use_container_width=True)
        prop = st.selectbox("Physicochemical property", ["isoelectric_point", "gravy", "aromaticity",
                                                         "instability_index", "molecular_weight_kda"])
        st.plotly_chart(px.box(fa, x="subcluster", y=prop, points="all", color="subcluster", color_discrete_map=cmap,
                               category_orders={"subcluster": sorted(cmap, key=group_key)}), use_container_width=True)
        st.markdown("**Conserved motif:** G-x-S-x-G (catalytic-serine motif of serine hydrolases) is present in "
                    f"{int((feats.gxsxg_count > 0).sum())} of {len(feats)} proteins.")
        st.image(str(C.FIGURES / "f09_gxsxg_motif_variants.png"), width=650)
    with t4:
        st.dataframe(comp, hide_index=True, use_container_width=True, height=300)
        st.image(str(C.FIGURES / "f04_clustering_method_comparison.png"))
        st.markdown("**Inside G1 (second level)**")
        st.dataframe(sub, hide_index=True, use_container_width=True, height=250)
        st.caption("Silhouette: −1..1, higher = better separated (< 0.25 = weak structure). Stability: mean adjusted "
                   "Rand index between full-data clusters and clusters of 30 random 80% subsamples (1 = identical).")
    with t5:
        page_network(a, cmap)


def page_network(a, cmap):
    st.warning("This is a **sequence-similarity network** - an edge means two proteins have similar amino-acid "
               "sequences. It is **not** a protein-protein interaction network.")
    nodes, edges, lay = load("network/ssn_nodes.csv"), load("network/ssn_edges.csv"), load("network/ssn_layout.csv")
    st.markdown(f"Edge rule: identity ≥ {100 * C.EDGE_MIN_IDENTITY:.0f}% **and** alignment covering ≥ "
                f"{100 * C.EDGE_MIN_COVERAGE:.0f}% of **both** proteins. 40% identity over most of two ~300-residue "
                "proteins is well above the 25-35% 'twilight zone', so edges indicate probable homology; the "
                "coverage rule stops a short shared segment (e.g. a signal peptide) from creating an edge. "
                f"Result: {len(nodes)} nodes, {len(edges):,} edges.")
    min_id = st.slider("Show edges with identity at least (%)", 40, 100, 60, 5)
    pos = lay.set_index("protein_id")
    e = edges[edges.identity >= min_id / 100]
    xs, ys = [], []
    for s, t in zip(e.source, e.target):
        xs += [pos.x[s], pos.x[t], None]
        ys += [pos.y[s], pos.y[t], None]
    fig = go.Figure(go.Scattergl(x=xs, y=ys, mode="lines", line=dict(width=0.4, color="rgba(120,120,120,0.35)"),
                                 hoverinfo="skip", showlegend=False))
    n = nodes.merge(lay, left_on="id", right_on="protein_id").merge(a[["protein_id", "subcluster"]], on="protein_id")
    for g in sorted(cmap, key=group_key):
        d = n[n.subcluster == g]
        fig.add_trace(go.Scattergl(x=d.x, y=d.y, mode="markers", name=g, marker=dict(size=7, color=cmap[g],
                                   line=dict(width=0.5, color="white")),
                                   text=d.protein_name + " | " + d.organism.fillna(""), hoverinfo="text"))
    fig.update_layout(height=600, xaxis=dict(visible=False), yaxis=dict(visible=False), plot_bgcolor="white",
                      title=f"Layout computed from all ≥40% edges; showing {len(e):,} edges ≥ {min_id}%")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(load("network/edge_threshold_sensitivity.csv"), hide_index=True, height=250)
    c1, c2 = st.columns(2)
    c1.download_button("⬇ Cytoscape nodes (ssn_nodes.csv)", (C.NETWORK / "ssn_nodes.csv").read_bytes(), "ssn_nodes.csv", "text/csv")
    c2.download_button("⬇ Cytoscape edges (ssn_edges.csv)", (C.NETWORK / "ssn_edges.csv").read_bytes(), "ssn_edges.csv", "text/csv")
    st.caption("Cytoscape: File → Import → Network from File → ssn_edges.csv (source = Source Node, target = Target "
               "Node, other columns = edge attributes); then File → Import → Table from File → ssn_nodes.csv "
               "(id = key) as node attributes.")


# --------------------------------------------------------------------------- page 3
def page_temperature():
    st.title("🌡️ Temperature Analysis")
    st.info("Rules: the highest tested temperature is **not** treated as the optimum. A 'best tested temperature' is "
            "only reported inside one comparable series (same paper, metric, unit, pH, duration, material, enzyme "
            "loading) with ≥ 3 temperatures - and is still only the best of the temperatures that were tried. "
            "Measurements with different units or methods are never compared directly.")
    assays = load("temperature/pet_temperature_assays.csv")
    assays = assays[assays.in_pet_active_set]
    summ = load("temperature/protein_temperature_summary.csv")
    series = load("temperature/comparable_temperature_series.csv")
    meas = load("temperature/pet_measurements.csv")
    groups = sorted(assays.subcluster.dropna().unique(), key=group_key)

    sel_groups = st.multiselect("Filter by sequence group", groups, default=groups)
    a = assays[assays.subcluster.isin(sel_groups)]
    s = summ[summ.subcluster.isin(sel_groups)]

    c = st.columns(4)
    c[0].metric("PET assays", f"{len(a):,}")
    c[1].metric("Proteins", s.protein_id.nunique())
    c[2].metric("Tested at 1 temperature", int((s.n_temperatures_tested == 1).sum()))
    c[3].metric("With comparable series (≥3 °C values)", int((s.n_comparable_series > 0).sum()))

    t1, t2, t3, t4 = st.tabs(["Overview graphs", "By protein", "Standardised screens", "Data table"])
    with t1:
        st.plotly_chart(px.histogram(a, x="temperature_c", nbins=40, color_discrete_sequence=[SERIES[0]],
                                     title="Temperatures at which PET assays were run"), use_container_width=True)
        d = a[a.degradation_detected.isin(["detected", "not detected"])].copy()
        d["temperature band"] = pd.cut(d.temperature_c, [0, 30, 40, 50, 60, 70, 80, 100], right=False,
                                       labels=["<30", "30-39", "40-49", "50-59", "60-69", "70-79", "≥80"])
        fig = px.histogram(d, x="temperature band", color="degradation_detected", barmode="stack",
                           color_discrete_map={"detected": SERIES[0], "not detected": SERIES[1]},
                           category_orders={"temperature band": ["<30", "30-39", "40-49", "50-59", "60-69", "70-79", "≥80"]},
                           title="PET degradation observations by temperature band (assay counts)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("'Not detected' assays come mostly from two large screening studies, so these shares reflect "
                   "study design as much as biology.")
        act = a[a.degradation_detected == "detected"].drop_duplicates(["protein_id", "temperature_c"])
        st.plotly_chart(px.strip(act, x="subcluster", y="temperature_c", color="subcluster",
                                 color_discrete_map=color_map(groups), hover_name="protein_name",
                                 category_orders={"subcluster": groups},
                                 title="Temperatures with detected activity by group (one point per protein × temperature)"),
                        use_container_width=True)
    with t2:
        names = s.sort_values("protein_name")
        pick = st.selectbox("Protein", names.protein_id, format_func=lambda i: f"{names.set_index('protein_id').protein_name[i]} (PAZy {i})")
        r = summ.set_index("protein_id").loc[pick]
        st.markdown(f"**Temperatures tested:** {r.temperatures_tested_c} °C  \n"
                    f"**With detected degradation:** {r.temperatures_with_activity_c if pd.notna(r.temperatures_with_activity_c) else '-'} °C  \n"
                    f"**Tested without detected degradation:** {r.temperatures_without_detected_activity_c if pd.notna(r.temperatures_without_detected_activity_c) else '-'} °C  \n"
                    f"**Optimum:** {r.temperature_optimum_status}")
        pa = assays[assays.protein_id == pick]
        st.plotly_chart(px.strip(pa, x="temperature_c", y="degradation_detected", color="degradation_detected",
                                 color_discrete_map={"detected": SERIES[0], "not detected": SERIES[1], "unclear": "#a3a29c"},
                                 title="Assay outcomes by temperature"), use_container_width=True)
        ps = series[(series.protein_id == pick) & ~series.all_zero]
        if len(ps):
            k = st.selectbox("Comparable series", range(len(ps)), format_func=lambda i: (
                f"{ps.iloc[i].metric_type} [{ps.iloc[i].unit}] · pH {ps.iloc[i].ph} · {ps.iloc[i].literature_doi}"))
            row = ps.iloc[k]
            df = pd.DataFrame({"temperature_c": [float(x) for x in row.temperatures_c.split("; ")],
                               "value": [float(x) for x in row["values"].split("; ")]})
            st.plotly_chart(px.line(df, x="temperature_c", y="value", markers=True,
                                    labels={"value": f"{row.metric_type} ({row.unit})"},
                                    title=f"Best tested temperature in this series: {row.best_tested_temperature_c:g} °C "
                                          f"({row.best_at_edge})"), use_container_width=True)
            if row.best_at_edge != "interior":
                st.caption("The best value is at the edge of the tested range - the true optimum may lie outside it.")
        else:
            st.caption("No comparable series with ≥ 3 temperatures for this protein.")
        pm = meas[meas.protein_id == pick][["temperature_c", "ph", "metric_type", "analyte", "value", "unit",
                                             "measurement_call", "material_name", "literature_doi", "reported_result"]]
        st.dataframe(pm, hide_index=True, use_container_width=True, height=250)
        st.markdown("**References:** " + doi_links(r.references))
    with t3:
        st.markdown("Only these two datasets compare many proteins under **one protocol**, so values can be compared "
                    "across proteins within each screen (not between the screens).")
        st.image(str(C.FIGURES / "t04_standardised_screen_d3.png"), width=600,
                 caption="DOI 10.1038/s41467-022-35237-x, Source Data Table D3")
        st.image(str(C.FIGURES / "t05_standardised_screen_40_vs_60.png"), width=600, caption="DOI 10.1021/acscatal.5c03460")
    with t4:
        st.dataframe(a, hide_index=True, use_container_width=True, height=450)
        st.download_button("⬇ Temperature dataset (CSV)", a.to_csv(index=False).encode(), "pet_temperature_assays.csv")


# --------------------------------------------------------------------------- page 4
def page_overview():
    st.title("📊 Dataset Overview")
    st.markdown(f"**Research question.** {RESEARCH_QUESTION}")
    st.markdown("\n".join(f"- {h}" for h in HYPOTHESES))
    p = proteins()
    o = load("organisms/protein_organisms.csv")
    assays = load("temperature/pet_temperature_assays.csv")
    c = st.columns(5)
    c[0].metric("PET-active proteins analysed", len(p))
    c[1].metric("PET assays (all proteins)", f"{len(assays):,}")
    c[2].metric("Publications", p.dois.str.split("; ").explode().nunique())
    c[3].metric("Organism known", f"{int((o.organism != UNKNOWN).sum())}/{len(o)}")
    c[4].metric("Usable PET-inactive sequences", 0)

    st.subheader("Data sources and provenance")
    st.dataframe(load_feasibility("tables/dataset_inventory.csv"), hide_index=True, use_container_width=True)
    st.caption("Original files in data/ are never modified. PAZy = Plastics-Active enZymes database; PlasticDB = "
               "plastic-degradation literature database; UniProt download dated 2026-10-27 (from file name). "
               "Download dates of the other files were not recorded.")

    st.subheader("Quality control")
    st.dataframe(load("clean/qc_checks.csv"), hide_index=True)
    st.dataframe(load_feasibility("pet_dataset_quality_summary.csv"), hide_index=True, use_container_width=True, height=300)

    st.subheader("Organism annotations")
    st.dataframe(load("organisms/organism_evidence_summary.csv"), hide_index=True)
    st.dataframe(o[["protein_id", "protein_name", "organism", "taxonomy_id", "organism_evidence", "confidence",
                    "isolation_environment", "evidence_detail"]], hide_index=True, use_container_width=True, height=300)

    st.subheader("Missing information")
    t = load("temperature/protein_temperature_summary.csv")
    st.markdown(f"""
- **Organism:** unknown for {int((o.organism == UNKNOWN).sum())} of {len(o)} proteins (no matching record in the provided files);
  {int(o.sources_disagree.sum())} proteins have database records that disagree; {int(o.uncultured_or_metagenomic.sum())} come from uncultured/metagenomic sources.
- **Isolation environment:** documented for only {int((o.isolation_environment != 'Not documented in provided files').sum())} proteins.
- **Temperature optimum:** {int((t.n_temperatures_tested <= 1).sum())} proteins tested at ≤ 1 temperature; {int((t.n_temperatures_tested == 2).sum())} at 2.
- **Negative class:** 0 PET-inactive proteins with sequences, so PET-active vs inactive classification is not possible.
- **Family annotations:** no Pfam/InterPro/ESTHER labels in the provided files.""")

    st.subheader("Biological interpretation and limitations")
    st.markdown("""
- **H1 supported.** 263 of 298 proteins (88%) form one sequence group (G1). 296 of 298 carry the G-x-S-x-G catalytic-serine motif,
  and G1 shares an extended version of it, G-x-S-M-G-G-G (5-mer SMGGG in 93% of G1, 3% elsewhere).
- **The rest are not tidy families.** Small groups G3 (GYSQG motif, ~228 aa) and G4 (~462 aa) are coherent. G2 and G5 are heterogeneous
  remainders (mean identity < 25%), and G6/G7 are single proteins.
- **H2 cannot be tested cleanly.** Temperatures with detected activity differ between groups, but each group was tested by different
  studies with different temperature ranges. Temperature differences may reflect experimental design, not enzyme biology.
- **Sampling bias.** G1b (98 proteins) comes almost entirely from three papers, mostly two large screening studies.
- **Clusters describe known PET hydrolases only.** Without inactive examples they cannot predict whether a new protein degrades PET.
""")


def main():
    pg = st.navigation([st.Page(page_search, title="Protein Search", icon="🔎", url_path="search", default=True),
                        st.Page(page_clusters, title="Protein Clusters", icon="🧩", url_path="clusters"),
                        st.Page(page_temperature, title="Temperature Analysis", icon="🌡️", url_path="temperature"),
                        st.Page(page_overview, title="Dataset Overview", icon="📊", url_path="overview")])
    st.sidebar.markdown("**PET Enzyme Explorer**  \nResearch dashboard - Computing for Bioinformatics")
    st.sidebar.caption("Experimental findings come from PAZy assay records. Sequence matches and clusters are "
                       "computational and must not be read as proof of PET degradation.")
    pg.run()


if __name__ == "__main__":
    main()
