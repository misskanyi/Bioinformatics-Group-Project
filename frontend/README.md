# PET Enzyme Explorer — web app

Next.js (App Router) + TypeScript + Tailwind CSS v4 front end for the PET Enzyme Explorer.
All data comes from the FastAPI backend in `../backend`; `/api/*` is proxied to it by
`next.config.ts` (`BACKEND_URL`, default `http://127.0.0.1:8000`).

```bash
# terminal 1, repository root
.venv/bin/uvicorn backend.main:app --port 8000
# terminal 2
cd frontend && npm install && npm run dev      # http://localhost:3000
```

Do not run `npm run build` while `npm run dev` is running: both use `.next/`.

## Structure

| Path | Contents |
|---|---|
| `app/` | Routes: `/dashboard`, `/sequence-lab`, `/networks`, `/conditions`, `/organisms`, `/datasets`, `/about` |
| `features/<page>/` | Page-level views and their components |
| `components/ui/` | Accessible primitives (shadcn/ui pattern on Radix: button, tooltip, tabs, slider, states) |
| `components/layout/` | App shell, collapsible sidebar, top bar with live backend health check |
| `components/viz/` | Cytoscape network, identity heatmap, helix canvas, shared chart styling |
| `lib/` | Typed API client with caching, colour tokens, helpers |
| `types/api.ts` | Response types mirroring `backend/api/*` |

## Design system

Colour tokens live in `app/globals.css` (`@theme`): `void` (#091321), `surface`, `elevated`,
`line`, `teal`, `cyan`, `mint`, `ink`, `muted`, `amber`. Evidence colours are fixed across the app
(`lib/palette.ts`): experimental = mint, computational similarity = cyan, documented organism =
violet, missing/uncertain = amber. Subgroups G1a–G7 each have one colour used by every chart.
Motion respects `prefers-reduced-motion`.

## Scientific integrity rules in the UI

- No PET-activity probability or confidence score is shown anywhere; identity is labelled as similarity.
- Organisms are shown only with their evidence level; similar proteins are context only.
- No temperature optimum is claimed; “best tested temperature” appears only inside a comparable series.
- The network is labelled as a sequence-similarity network, not a protein–protein interaction network.
