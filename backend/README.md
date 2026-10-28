# PET Enzyme Explorer — API

FastAPI service behind the web app in `../frontend`. It serves the cached outputs of
`python -m pet_explorer.pipeline` and runs live sequence matching with
`pet_explorer.sequence_matching`. No scientific result is recomputed here.

```bash
# from the repository root
.venv/bin/pip install -r requirements.txt -r backend/requirements.txt
.venv/bin/python -m pet_explorer.pipeline          # once, if outputs/explorer/ is missing
.venv/bin/uvicorn backend.main:app --port 8000
.venv/bin/pytest backend/tests -q
```

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Real readiness check (tables + matcher loaded) |
| `GET /api/overview` | Landing-page statistics and generated insights |
| `GET /api/proteins`, `/api/proteins/{id}` | Reference protein index and evidence card |
| `GET /api/sequence/examples`, `POST /api/sequence/match` | Example reference sequences; Smith–Waterman matching |
| `GET /api/network?min_identity=&min_coverage=` | Similarity network re-filtered from the all-vs-all alignment table |
| `GET /api/clustering` | PCA / MDS coordinates, composition, cluster summary, identity heatmap |
| `GET /api/conditions` | PET assay records, per-protein temperature summary, comparable series |
| `GET /api/organisms` | Organisms with evidence level; unknowns with context-only relatives |
| `GET /api/datasets` | Provenance pipeline, quality metrics, coverage, limitations, references |
| `GET /api/downloads/{key}` | Whitelisted processed files (Cytoscape node/edge CSV, FASTA, tables) |

Layout:

- `main.py` — app, CORS, gzip, startup warm-up
- `api/` — one router per page of the web app
- `services/store.py` — cached read-only access to `outputs/`
- `services/matching.py` — wrapper around the validated matcher
- `services/layout.py` — display-only network layout (per-component, packed)
