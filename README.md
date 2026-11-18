# PET Enzyme Explorer

*A bioinformatics and machine-learning system for identifying and characterising PET-degrading enzymes*
(Computing for Bioinformatics, year-4 semester project).

[![CI](https://github.com/misskanyi/Bioinformatics-Group-Project/actions/workflows/ci.yml/badge.svg)](https://github.com/misskanyi/Bioinformatics-Group-Project/actions/workflows/ci.yml)

## Research question

> **How can protein sequence analysis and machine learning help identify promising PET-degrading enzyme candidates
> for further laboratory testing?**

It is answered through four supporting investigations:

| Investigation | What it contributes | Where |
|---|---|---|
| Sequence analysis | Places any sequence relative to 298 enzymes with published PET activity (alignment, shuffle control, catalytic motif) | Notebook §5, §7.3; *Single Sequence* and *Bulk Analysis* pages |
| Clustering | Shows the verified PET hydrolases form real, stable sequence groups, so a candidate's group says what it resembles | Notebook §5.2–5.4, §6, §7.1; *Exploratory Analysis*, *Similarity Network* |
| Assay conditions | Tests whether those groups differ in the temperatures at which activity was observed | Notebook §5.5–5.6; *Assay Conditions* |
| Supervised learning | Tests whether sequence features predict activity at one named condition well enough to rank candidates | Notebook §7.2; *Model Validation* |

**Objectives** (wording used in the notebook; the web app's Overview page uses a different O1–O4 wording, and the
two are to be aligned once the approved wording is confirmed):

1. **O1 — Data:** a clean, quality-controlled set of experimentally verified PET-active enzyme sequences, linked to
   assay conditions and documented source organisms.
2. **O2 — Sequence groups:** group the enzymes by sequence, test the groups against chance, and interpret them with
   domain annotation and the literature.
3. **O3 — Temperature:** test whether the groups differ in the temperatures at which PET degradation was detected,
   with FDR correction, separating real differences from study design.
4. **O4 — Machine learning:** evaluate the clustering against null baselines, and a supervised model of activity at
   60 °C against proper baselines.

**Hypotheses:** H1 most verified PET hydrolases share one motif-bearing lineage (*supported*); H2 groups differ in the
temperatures at which activity was detected (*not confirmed* once study design is controlled); H3 sequence features
predict detection at 60 °C better than baselines (*not supported*).

## What the system can and cannot conclude

| It can say | It cannot say |
|---|---|
| How similar a sequence is to characterised PET hydrolases (identity, coverage of both sequences, shuffle z-score) and whether it carries the G-x-S-x-G catalytic motif | Whether the sequence degrades PET. No probability of activity is given anywhere. |
| What experimental evidence exists **for the matched reference enzyme** (assays, conditions, papers) | That the reference's evidence transfers to the query: that is a hypothesis, weaker at lower identity |
| Which sequence group a protein most resembles, and which groups are real structure | That groups differ in temperature behaviour (H2 not confirmed) |
| Which untested candidates have the strongest **sequence** case for laboratory testing (shortlist) | That any shortlisted candidate is active. Only an assay can confirm activity. |
| That the supervised 60 °C model does **not** beat its shuffled-label null (ROC AUC 0.556, permutation p = 0.32) | Anything from that model's scores: it ranks nothing in this project |

Red means "no convincing similarity", never "PET-inactive": the data contain no confirmed PET-inactive sequences.

## Main results

- **298** experimentally verified PET-active proteins (from 301 in PAZy); 5,058 PET assay records; **0** usable
  PET-inactive sequences.
- **Clustering:** 7 alignment-based groups, silhouette 0.344 vs ≤ 0.03 for null models (p = 0.005); G1 (88%) is the
  PET hydrolase/cutinase family (Pfam PF12740).
- **Temperature:** apparent group differences disappear under one standardised protocol (q ≥ 0.08).
- **Supervised model (60 °C, 78 proteins, 19 identity groups):** best ROC AUC 0.556 ± 0.09 under 20 × grouped 5-fold
  CV; per-fold, ROC-curve, confusion-matrix and F1 views agree; permutation p = 0.32. **Not a working predictor.**
- **Shortlist:** of 254 untested annotation-only candidates, **8** have the strongest sequence case and **20** are
  possible but weaker; 104 near-identical ones turned out to be already-characterised enzymes under another record.

## Repository layout

| Path | Contents |
|---|---|
| `data/` | Raw downloads, **never modified**: PAZy (CSV, FASTA, assay JSON), PlasticDB (FASTA, degraders list), UniProt FASTA, ACS Catalysis 2025 screen workbook, 33 PETML study workbooks + `sequences.fasta`; `data/samples/` holds three demo CSVs for Bulk Analysis |
| `analyze_pet_dataset.py` | Feasibility analysis: assay classification and protein labelling |
| `pet_explorer/` | Analysis package: `preprocess`, `sequence_matching`, `similarity`, `features`, `clustering`, `network`, `temperature`, `organisms`, `annotation`, `prediction`, `evidence`, `curation`, `shortlist`, `plots`, `pipeline`, `config` |
| `notebooks/pet_enzyme_explorer.ipynb` | **Submission notebook** (8 stages, saved outputs); generated by `notebooks/build_notebook.py` |
| `outputs/` | Cached results (tables, figures, reports); `outputs/explorer/` is read by the web app |
| `backend/` | FastAPI service: serves cached outputs and runs live sequence matching |
| `frontend/` | Next.js web app |
| `tests/`, `backend/tests/` | Scientific and API test suites |
| `scripts/` | `check_notebook.py` (validates an executed notebook), `compare_outputs.py` (rebuild vs reference) |
| `.github/workflows/` | GitHub Actions: `ci.yml`, `full-verification.yml` |

## Installation

Requirements: Python 3 (tested locally with 3.9 and 3.11; CI uses 3.12, the Colab version), Node.js (tested with
22, which CI also uses; Next.js 15 needs at least 18.18) and npm.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r backend/requirements.txt   # analysis + API
cd frontend && npm ci && cd ..                                          # web app (exact lockfile versions)
```

## Run the notebook in Google Colab

1. Open Colab → *File → Open notebook → GitHub*, enter `misskanyi/Bioinformatics-Group-Project`, choose
   `notebooks/pet_enzyme_explorer.ipynb`.
2. *Runtime → Run all*. The first code cell clones the repository (branch set by `REPO_BRANCH`, default `main`) and
   installs Biopython; everything else is preinstalled in Colab. Locally, a run on the cached outputs takes about
   10 seconds; Colab timing has not been measured yet.
3. To rebuild every analysis output inside the notebook, set `RECOMPUTE = True` in the setup cell (or run with the
   environment variable `PET_RECOMPUTE=1`). This takes about 1–2 minutes on 10 cores and longer on Colab's 2 cores.

The notebook prints the library versions it ran with. **Status:** the notebook has been executed end to end locally
(Python 3.9 and a clean Python 3.11 environment) and in a clean clone with full recomputation. Execution in Google
Colab itself has **not yet been verified**; please run it there once and record the result.

## Reproduce the analysis from the raw data

```bash
.venv/bin/python analyze_pet_dataset.py            # 1. assay classification + protein labels (~15 s)
.venv/bin/python -m pet_explorer.curation          # 2. candidate registry, condition labels, grouped splits (~100 s)
.venv/bin/python -m pet_explorer.pipeline          # 3. clean set, alignments, clustering, temperature, organisms,
                                                   #    network, null baselines, 60 °C model, domains (~1–5 min)
.venv/bin/python -m pet_explorer.shortlist         # 4. laboratory shortlist from sequence evidence (~1 min)
.venv/bin/python -m pet_explorer.evidence          # 5. (optional) recalibrate the evidence-rule thresholds

# rebuild and execute the notebook
.venv/bin/python notebooks/build_notebook.py
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/pet_enzyme_explorer.ipynb
```

`--stage N` runs one pipeline stage; `--refresh-annotation` re-queries UniParc (the only step that needs network
access; its results are cached in `outputs/explorer/annotation/`).

## Run the web app

```bash
.venv/bin/uvicorn backend.main:app --port 8000      # terminal 1, repository root; health: http://127.0.0.1:8000/api/health
cd frontend && npm run dev                          # terminal 2; open http://localhost:3000
```

The front end proxies `/api/*` to `BACKEND_URL` (default `http://127.0.0.1:8000`). If the front end is served from
another origin, add it to `PET_EXPLORER_ORIGINS` (comma-separated). Production build: `cd frontend && npm run build &&
npm run start`. The API only reads cached files in `outputs/`, so run the analysis first if they are missing.

Troubleshooting: *backend offline* in the top bar → check terminal 1 and `/api/health`; port in use → `--port 8001`
and `BACKEND_URL=http://127.0.0.1:8001 npm run dev`.

## Tests

```bash
.venv/bin/python -m pytest -q tests                 # scientific tests, incl. tests/test_reproducibility.py
.venv/bin/python -m pytest -q backend/tests         # API tests
cd frontend && npx tsc --noEmit && npm run lint && npm run build
.venv/bin/python scripts/check_notebook.py notebooks/pet_enzyme_explorer.ipynb
```

`tests/test_reproducibility.py` recomputes small slices of the analysis and compares them with the cached outputs
using tolerances: raw-data schema, deterministic preprocessing, alignment scores, the leave-one-out table,
homology-aware fold separation (no identity group and no ≥ 70%-identical pair crosses a fold), consistency between the
per-fold and summary metrics, the permutation null, absence of model files or probability columns, and recomputation of
shortlist rows.

## Continuous integration (GitHub Actions)

| Workflow | Runs on | What it does |
|---|---|---|
| `ci.yml` — *CI* | push to `main` or `feature/**`, pull requests into `main`, manual | **Python tests** (Python 3.12, JUnit reports uploaded); **Frontend** (`npm ci`, `tsc --noEmit`, ESLint, `next build`); **Notebook** (executes the notebook on cached outputs, fails on any cell error, validates the eight stages, the research question and ≥ 3 EDA plots drawn in code, checks the generator and notebook are in sync, uploads the executed notebook and logs) |
| `full-verification.yml` — *Full scientific verification* | manual (*Actions → Run workflow*) and weekly | Deletes every regenerable output, rebuilds it from `data/` (feasibility, curation, the notebook with `PET_RECOMPUTE=1`, calibration), compares the results with the committed outputs using per-file tolerances (`scripts/compare_outputs.py`), runs the tests on the rebuilt files and uploads the comparison report, logs and executed notebook |

Dependencies are cached by `actions/setup-python` (pip) and `actions/setup-node` (npm, keyed on
`frontend/package-lock.json`). Workflows have read-only repository permissions and use no secrets.

## Evidence indicators (green / yellow / red / grey)

Single Sequence and Bulk Analysis show a **sequence-based evidence assessment** for every protein. It is not a
machine-learning prediction and not a probability of PET activity. Both interfaces, and the shortlist, call the same
code (`pet_explorer/evidence.assess`) with the same 25 composition-preserving shuffles and seed.

| Colour | Meaning | Main rules (top hit vs. 298 curated PET-active proteins) |
|---|---|---|
| Green | Likely PET-degrading candidate | Identical to a reference (rule K), or ≥ 40 % identity and ≥ 70 % coverage of both sequences, shuffle z ≥ 15, G-x-S-x-G present, reference with positive assays and high label confidence (H1) |
| Yellow | Possible candidate | Homolog missing the motif or with a medium-confidence reference (H2); partial coverage (P); twilight zone with z ≥ 15 (T1); domain-level or remote similarity with z ≥ 15 (D1, D2) |
| Red | Unlikely based on current evidence | No similarity band (or twilight band) **and** z ≤ 9 (N2, T3). Never means "PET-inactive". |
| Grey | Insufficient evidence | Homolog-level identity with z < 15 (H3), 9 < z < 15 (T2, N1), fragments (F), short local matches (L) |

Calibration (`python -m pet_explorer.evidence`): shuffled reference sequences reach at most z = 10.2 and are assessed
294 red / 4 insufficient / 0 yellow / 0 green; leave-one-out searches of the 298 references give 249 green / 43 yellow /
4 insufficient / 2 red. The full rule table is served at `/api/evidence/rules`.

**Sample datasets** (`data/samples/`): on *Enzyme Prediction & Discovery → Bulk Analysis*, **Analyse Dataset**
submits the CSV through the normal upload pipeline and **Download CSV** saves it.
`01_Known_PET_Enzymes.csv` (IsPETase, LCC, TfCut2), `02_Positive_vs_Unrelated.csv` (IsPETase, LCC, human haemoglobin β),
`03_Low_Evidence_Controls.csv` (haemoglobin β and two synthetic repeat sequences).

## Cytoscape

1. **File → Import → Network from File** → `outputs/explorer/network/ssn_edges.csv` (source / target).
2. **File → Import → Table from File** → `ssn_nodes.csv` (key `id`).

Edges: ≥ 40 % identity over ≥ 70 % of both proteins. This is a **sequence-similarity network**, not a protein–protein
interaction network.

## Deployment status

**Implemented:** local development setup (FastAPI on port 8000, Next.js on port 3000) and GitHub Actions CI.
**Not implemented:** no hosted deployment, no cloud resources, no authentication. Any AWS EC2 or other hosting in
project proposals is **proposed infrastructure only**.
