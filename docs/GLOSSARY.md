# Glossary

Plain-language definitions of the terms used in the README, the notebook and the PET Enzyme Explorer app. Use it when
reading the results or presenting the project to someone outside bioinformatics.

## Biology

| Term | Meaning in this project |
|---|---|
| **PET** | Polyethylene terephthalate, the plastic used in drinks bottles and polyester fibres. The project looks for enzymes that can break it down. |
| **PET hydrolase** | An enzyme that breaks the ester bonds in PET using water. Well-known examples in the sample data are IsPETase, LCC and TfCut2. |
| **Cutinase** | An enzyme family that naturally breaks down cutin, the waxy coating on plant leaves. Many PET hydrolases belong to it, which is why the largest group (G1) is described as the "PET hydrolase/cutinase family". |
| **Catalytic motif (G-x-S-x-G)** | A short amino-acid pattern, Gly–any–Ser–any–Gly, found around the active-site serine of serine hydrolases. Having it is consistent with hydrolase activity, but does not prove it. |
| **Assay** | A laboratory experiment that measures whether, and how well, an enzyme degrades PET under given conditions (temperature, substrate form and so on). Only an assay can confirm activity. |
| **Homolog** | A protein that shares ancestry with another, usually recognised by clear sequence similarity. |
| **Pfam family** | A curated database grouping of protein domains that share a common origin. The README links G1 to Pfam PF12740. |

## Data sources

| Term | Meaning |
|---|---|
| **PAZy** | Plastics-Active Enzymes Database. Source of the 298 verified PET-active proteins and their assay records. |
| **PlasticDB** | A database of microorganisms and proteins reported to degrade plastics. |
| **UniProt / UniParc** | The main public protein sequence and annotation databases. UniParc is queried for annotations of candidate sequences. |
| **PETML** | A collection of published PET-activity studies with measured results. The project uses 33 of its study workbooks plus `sequences.fasta`, stored in `data/`. |
| **Annotation-only candidate** | A protein labelled as a possible PET enzyme in a database, with no verified assay record in the project's sources. |

## Sequence analysis

| Term | Meaning |
|---|---|
| **Smith–Waterman alignment** | An algorithm that finds the best-matching *local* region between two sequences, so a partial match is still found. |
| **Percent identity** | The share of aligned positions where both sequences have the same amino acid. |
| **Coverage (of both sequences)** | How much of each protein the alignment spans. High identity over a short stretch is weak evidence, so the app checks coverage of both the query and the reference. |
| **Shuffle z-score** | How far the real alignment score sits above the scores of shuffled versions of the same sequence (same amino-acid composition, random order), in standard deviations. A high z means the similarity is unlikely to be chance. The app uses 25 shuffles. |
| **Twilight zone** | Roughly 20–35 % identity, where real relationships and chance similarity are hard to tell apart. The evidence rules treat this band cautiously. |
| **Sequence similarity network (SSN)** | A graph where each node is a protein and an edge joins two proteins with ≥ 40 % identity over ≥ 70 % of both. It shows sequence relationships, *not* physical protein–protein interactions. |
| **Evidence indicator** | The green / yellow / red / grey label shown for a sequence. It summarises sequence evidence and is **not** a probability of PET activity. Red means "no convincing similarity", never "PET-inactive". |

## Clustering and statistics

| Term | Meaning |
|---|---|
| **Clustering** | Grouping proteins so that members of a group are more similar to each other than to other groups. The project finds 7 groups from alignment scores. |
| **Silhouette score** | A measure of how well separated clusters are, from −1 to 1. Higher is better. The project's 0.344 is compared with ≤ 0.03 for random (null) groupings. |
| **Null model / baseline** | What you would expect by chance, for example shuffled labels or random groups. A result only means something if it beats its null. |
| **Permutation test (p-value)** | Repeats the analysis many times with labels shuffled to see how often chance does as well as the real result. p = 0.32 means chance matched the model about a third of the time, so the model is not better than chance. |
| **q-value** | A p-value adjusted for running many tests at once. It controls how many false discoveries you expect among the significant results. |
| **ROC AUC** | How well a model ranks positives above negatives: 1.0 is perfect, 0.5 is a coin flip. The 60 °C model's mean of 0.556 is close to chance. |
| **Grouped cross-validation** | Testing a model on folds where closely related proteins (identity groups) are never split between training and test. This stops near-duplicate sequences from inflating the score. |
| **Mean fold vs pooled out-of-fold AUC** | The first averages the AUC computed inside each test fold. The second pools every fold's predictions into one AUC. They can differ because scores from different folds are on different scales. |

## Software

| Term | Meaning |
|---|---|
| **Cached outputs** | Results already computed and saved in `outputs/`. The notebook and web app read these, so they run in seconds. Setting `PET_RECOMPUTE=1` rebuilds them from `data/`. |
| **FastAPI backend** | The Python web service in `backend/` that serves the cached results and runs live sequence matching. |
| **Next.js frontend** | The web app in `frontend/` that users interact with. |
| **CI (GitHub Actions)** | Automated checks that run the tests, build the frontend and execute the notebook on every push or pull request. |
