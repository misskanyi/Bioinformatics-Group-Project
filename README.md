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

## Quick start: run the web app

Requirements: Python 3.9+, Node.js 18.18+ and npm.

```bash
# 1. One-time setup (repository root)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r backend/requirements.txt
cd frontend && npm install && cd ..

# 2. Generate analysis outputs (skip if outputs/explorer/ already exists) - ~5 min
.venv/bin/python analyze_pet_dataset.py
.venv/bin/python -m pet_explorer.pipeline

# 3. Terminal 1 - start the API (repository root)
.venv/bin/uvicorn backend.main:app --port 8000      # health check: http://127.0.0.1:8000/api/health

# 4. Terminal 2 - start the front end
cd frontend && npm run dev                          # open http://localhost:3000
```

Both servers must be running. The front end proxies `/api/*` to the backend at `BACKEND_URL`
(default `http://127.0.0.1:8000`); if the API runs elsewhere, start the front end with
`BACKEND_URL=http://host:port npm run dev`. If the front end is served from a different origin, add it to the
backend's allowed origins with `PET_EXPLORER_ORIGINS` (comma-separated, default `http://localhost:3000,http://127.0.0.1:3000`).

Production build: `cd frontend && npm run build && npm run start` (stop `npm run dev` first; both use `.next/`).

**Troubleshooting**

- Top bar shows the backend as offline → check terminal 1 is running and `/api/health` responds.
- API errors about missing files → run step 2; the API only reads cached files in `outputs/explorer/`.
- Port in use → `uvicorn ... --port 8001` and `BACKEND_URL=http://127.0.0.1:8001 npm run dev`, or `npm run dev -- -p 3001`
  (then add `http://localhost:3001` to `PET_EXPLORER_ORIGINS`).

## Evidence indicators (green / yellow / red)

Single Sequence and Bulk Analysis show a **sequence-based evidence assessment** for every analysed protein. It is
not a machine-learning prediction and not a probability of PET activity; the ML panel stays unavailable until a
model passes homology-aware validation.

Both interfaces call the same code (`backend/services/matching.run_search` → `pet_explorer/evidence.assess`), with
the same 25 composition-preserving shuffles and seed, so a sequence always gets the same result.

| Colour | Meaning | Main rules (top hit vs. 298 curated PET-active proteins) |
|---|---|---|
| Green | Likely PET-degrading candidate | Identical to a reference (**known characterised reference**, rule K), or ≥ 40 % identity and ≥ 70 % coverage of both sequences, shuffle z ≥ 15, G-x-S-x-G present, reference has positive assays with high label confidence (H1) |
| Yellow | Possible candidate | Homolog missing the motif or with a medium-confidence reference (H2); partial coverage (P); twilight zone with z ≥ 15 (T1); domain-level or remote similarity with z ≥ 15 (D1, D2) |
| Red | Unlikely based on current evidence | No similarity band (or twilight band) **and** z ≤ 9, i.e. within the range of shuffled sequences (N2, T3). Never means "PET-inactive". |
| Grey | Insufficient evidence | Signals disagree or are partial: homolog-level identity with z < 15 (H3), 9 < z < 15 (T2, N1), fragments (F), short local matches (L) |

Thresholds come from `python -m pet_explorer.evidence` (writes `outputs/explorer/matching/evidence_calibration*.{csv,json}`):
shuffled reference sequences reach at most z = 10.2 (99th percentile 9.0) and are assessed 294 red / 4 insufficient /
0 yellow / 0 green; leave-one-out searches of the 298 known PET-active proteins give 249 green / 43 yellow /
4 insufficient / 2 red. Identity alone never decides a colour, the catalytic motif can only lower one, and protein
names are never read. The full rule table is served at `/api/evidence/rules` and shown under "How are the colours
assigned?" in the app.

**Sample datasets** (`data/samples/`, listed at `/api/batch/samples`): on *Enzyme Prediction & Discovery → Bulk
Analysis*, each card's **Analyse Dataset** downloads the CSV and submits it through the normal upload pipeline;
**Download CSV** saves the file.

1. `01_Known_PET_Enzymes.csv` — IsPETase, LCC, TfCut2
2. `02_Positive_vs_Unrelated.csv` — IsPETase, LCC, human haemoglobin β (HBB)
3. `03_Low_Evidence_Controls.csv` — HBB and two synthetic repeat sequences

## Setup (analysis only)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run the analysis pipeline and tests

From the project root:

```bash
# 1. Feasibility analysis (labels every PET assay/protein) - ~15 s
.venv/bin/python analyze_pet_dataset.py

# 2. Explorer analysis: clean set, alignments, clustering, temperature + tests, organisms, network,
#    then stage 5: null baselines, supervised model, domain annotation - ~5 min
.venv/bin/python -m pet_explorer.pipeline          # all stages
.venv/bin/python -m pet_explorer.pipeline --stage 3   # one stage (needs earlier outputs)
.venv/bin/python -m pet_explorer.pipeline --stage 5 --refresh-annotation   # re-query UniParc

# 3. Notebook (rebuild + execute)
.venv/bin/python notebooks/build_notebook.py
cd notebooks && ../.venv/bin/jupyter nbconvert --to notebook --execute --inplace pet_enzyme_explorer.ipynb

# 4. Tests (input validation, matching, outputs, statistics, baselines)
.venv/bin/python -m pytest -q tests
.venv/bin/python -m pytest -q backend/tests      # API tests (needs backend/requirements.txt)

# 5. Front-end lint
cd frontend && npm run lint
```

## Google Colab

Open `notebooks/pet_enzyme_explorer.ipynb` in Colab (File → Open notebook → GitHub) and choose *Runtime → Run all*.
The first cell clones this repository (raw data and cached outputs) and installs Biopython; nothing else is needed.
The repository must be public, or Colab must be authorised to read it.

## Notebook structure (follows the project brief)

1. Question, objectives (O1–O4), hypotheses (H1–H3) · 2. Data acquisition and data dictionary · 3. Pre-processing and
QC · 4. EDA · 5. Core analysis: alignment, clustering, motifs, temperature, statistical tests with FDR ·
6. Biological interpretation: Pfam domains, literature, similarity network, organisms · 7. Machine learning: clustering
vs null baselines, supervised 60 °C model vs baselines, sequence matcher · 8. Conclusions per objective.

## Layout

| Path | Contents |
|---|---|
| `data/` | Six original downloads (PAZy, PlasticDB, UniProt). **Never modified.** |
| `analyze_pet_dataset.py` | Feasibility analysis and assay/protein activity labelling |
| `pet_explorer/` | Reusable modules: `preprocess`, `sequence_matching`, `similarity`, `features`, `clustering`, `network`, `temperature`, `organisms`, `annotation`, `prediction`, `plots`, `pipeline`, `config` |
| `notebooks/pet_enzyme_explorer.ipynb` | Reproducible scientific analysis with interpretations |
| `backend/` | FastAPI service: serves cached outputs and live sequence matching |
| `frontend/` | Next.js web app (the project's user interface) |
| `tests/` | pytest suite |
| `outputs/` | Feasibility outputs (`pet_dataset_feasibility_report.md`, …) |
| `outputs/explorer/clean/` | Cleaned 298-protein set (CSV + FASTA), QC checks |
| `outputs/explorer/clustering/` | Pairwise alignments, features, method comparison, assignments, summaries, null baselines |
| `outputs/explorer/network/` | **Cytoscape files** `ssn_nodes.csv`, `ssn_edges.csv`, threshold sensitivity, layout, centrality |
| `outputs/explorer/temperature/` | Assay- and measurement-level temperature datasets, comparable series, per-protein summary, statistical tests (BH-FDR) |
| `outputs/explorer/annotation/` | Pfam/InterPro matches from UniParc (cached), domains per group, literature comparison |
| `outputs/explorer/prediction/` | Supervised 60 °C model: dataset, model vs baseline comparison, permutation test, feature importance |
| `outputs/explorer/organisms/` | Per-protein organism table and per-source evidence links |
| `outputs/explorer/figures/` | Static figures used in the notebook |
| `outputs/explorer/FINDINGS.md` | Summary of findings and features needing more data |

The web app (`backend/` + `frontend/`) is a read-only consumer of `outputs/explorer/`, so run the pipeline first. See [Quick start](#quick-start-run-the-web-app);
endpoint and structure details are in [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md). Its Python dependencies are in
`backend/requirements.txt`, kept separate from the root `requirements.txt`. `backend/tests` check the API against
the output CSVs, so renaming columns in `outputs/explorer/` will break them.

## Cytoscape

1. **File → Import → Network from File** → `outputs/explorer/network/ssn_edges.csv` (source / target).
2. **File → Import → Table from File** → `ssn_nodes.csv` (key `id`).

Edges: ≥ 40% identity over ≥ 70% of both proteins. This is a **sequence-similarity network**, not a
protein–protein interaction network.
