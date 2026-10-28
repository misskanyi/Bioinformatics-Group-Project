# PET Enzyme Explorer

*A bioinformatics and machine-learning system for identifying and characterising PET-degrading enzymes*
(Computing for Bioinformatics, year-4 semester project).

Enter a protein sequence and get:
1. the closest experimentally characterised PET-active enzymes;
2. their sequence group;
3. reported test temperatures and PET-degradation evidence;
4. documented organisms.

The system keeps **experimental findings** (PAZy assay records) separate from **computational predictions**
(similarity, clusters). A close match is a *promising candidate*, not proof of PET degradation.

**Research question:** Do experimentally verified PET-hydrolysing enzymes form distinct groups based on their
amino-acid sequence features, and do these groups relate to the temperatures at which PET degradation was observed?

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

From the project root:

```bash
# 1. Feasibility analysis (labels every PET assay/protein) - ~15 s
.venv/bin/python analyze_pet_dataset.py

# 2. Explorer analysis: clean set, alignments, clustering, temperature, organisms, network - ~1 min
.venv/bin/python -m pet_explorer.pipeline          # all stages
.venv/bin/python -m pet_explorer.pipeline --stage 3   # one stage (needs earlier outputs)

# 3. Dashboard (reads cached outputs only)
.venv/bin/streamlit run app/streamlit_app.py

# 4. Notebook (rebuild + execute)
.venv/bin/python notebooks/build_notebook.py
cd notebooks && ../.venv/bin/jupyter nbconvert --to notebook --execute --inplace pet_enzyme_explorer.ipynb

# 5. Tests (25: input validation, matching, outputs, dashboard pages)
.venv/bin/python -m pytest -q tests
```

## Layout

| Path | Contents |
|---|---|
| `data/` | Six original downloads (PAZy, PlasticDB, UniProt). **Never modified.** |
| `analyze_pet_dataset.py` | Feasibility analysis and assay/protein activity labelling |
| `pet_explorer/` | Reusable modules: `preprocess`, `sequence_matching`, `similarity`, `features`, `clustering`, `network`, `temperature`, `organisms`, `plots`, `pipeline`, `config` |
| `app/streamlit_app.py` | Dashboard: Protein Search, Protein Clusters, Temperature Analysis, Dataset Overview |
| `notebooks/pet_enzyme_explorer.ipynb` | Reproducible scientific analysis with interpretations |
| `tests/` | pytest suite |
| `outputs/` | Feasibility outputs (`pet_dataset_feasibility_report.md`, …) |
| `outputs/explorer/clean/` | Cleaned 298-protein set (CSV + FASTA), QC checks |
| `outputs/explorer/clustering/` | Pairwise alignments, features, method comparison, assignments, summaries |
| `outputs/explorer/network/` | **Cytoscape files** `ssn_nodes.csv`, `ssn_edges.csv`, threshold sensitivity, layout |
| `outputs/explorer/temperature/` | Assay- and measurement-level temperature datasets, comparable series, per-protein summary |
| `outputs/explorer/organisms/` | Per-protein organism table and per-source evidence links |
| `outputs/explorer/figures/` | Static figures used in the notebook |
| `outputs/explorer/FINDINGS.md` | Summary of findings and features needing more data |

`backend/` (FastAPI) and `frontend/` (Next.js) contain a separate web app built in a parallel session. It is a
read-only consumer of `outputs/explorer/`, so run the pipeline first. Run commands are in
[backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md). Its Python dependencies are in
`backend/requirements.txt`, kept separate from the root `requirements.txt`. `backend/tests` check the API against
the output CSVs, so renaming columns in `outputs/explorer/` will break them.

## Cytoscape

1. **File → Import → Network from File** → `outputs/explorer/network/ssn_edges.csv` (source / target).
2. **File → Import → Table from File** → `ssn_nodes.csv` (key `id`).

Edges: ≥ 40% identity over ≥ 70% of both proteins. This is a **sequence-similarity network**, not a
protein–protein interaction network.
