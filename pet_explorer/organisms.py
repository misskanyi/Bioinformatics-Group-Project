"""Feature 4 - organism identification from the six local files only.

Evidence used, strongest first:
  1. exact_sequence      identical sequence in PlasticDB, degraders_list or UniProt
  2. contained_sequence  PAZy sequence lies inside a reference sequence, or vice
                         versa, overlap >= 100 aa. In this dataset every such match
                         covers >= 81% of the longer sequence, i.e. precursor vs
                         mature form (signal peptide) rather than a shared fragment.
  3. pazy_curation_text  "<enzyme> from <Genus species>" in PAZy's per-assay
                         curation notes (literature-reported, not sequence-checked)

Never used as the producing organism:
  * expression hosts (E. coli, B. subtilis WB800 ...) recorded for recombinant enzymes
  * organisms of similar sequences - shown separately as "closest characterised
    relative", explicitly labelled as context, not as the source organism.

Tax IDs come from degraders_list (NCBI Tax ID column) or UniProt (OX=). For a
PlasticDB-only match, a Tax ID is added when the identical organism name occurs
in degraders_list (marked as a name-based lookup). Isolation sample/environment/
location are copied only from matched degraders_list rows (documented values).

Outputs (outputs/explorer/organisms/):
  organism_links.csv     one row per protein x source record
  protein_organisms.csv  one row per protein (all 298)
"""

import gzip
import json
import re
from collections import defaultdict

import pandas as pd
from Bio import SeqIO

from . import config as C, preprocess

UNKNOWN = "Unknown — insufficient evidence"
NOT_DOCUMENTED = "Not documented in provided files"
CURATION_KEYS = ["protein_identity", "enzyme_identity", "identity_evidence", "reported_origin",
                 "enzyme_identity_in_publication", "enzyme_source_note", "source_strain", "enzyme_origin"]
FROM_PATTERN = re.compile(r"\bfrom (?:the )?(?:[a-z]+ )?([A-Z][a-z]+ (?:sp\.|[a-z]{3,})(?: (?:strain )?[A-Z0-9][\w-]*)?)")
HOST_WORDS = re.compile(r"recombinant|expressed in|expression host|E\. coli|Escherichia coli", re.I)
MIN_OVERLAP = 100
LEVELS = ["exact_sequence", "contained_sequence", "pazy_curation_text"]
CONFIDENCE = {"exact_sequence": "high", "contained_sequence": "medium-high", "pazy_curation_text": "medium"}
ASSOCIATION = {
    "exact_sequence": "Directly documented: sequence identical to a database record",
    "contained_sequence": "Directly documented: sequence overlaps a database record (precursor/mature form)",
    "pazy_curation_text": "Reported in the literature (PAZy curation text); not sequence-verified",
}


def _clean(v):
    return "" if pd.isna(v) else str(v).strip()


def _reference_sequences():
    """List of dicts: source, organism, taxid, accession, record, sequence, isolation fields."""
    refs = []
    for r in SeqIO.parse(C.F_PLASTICDB, "fasta"):
        rid, enz, org, plastics, gb = r.id.split("|")
        refs.append({"source": "PlasticDB", "organism": org.replace("_", " ").strip(), "taxid": None,
                     "accession": None if gb == "NA" else gb,
                     "record": f"{rid} ({enz.replace('_', ' ')}; plastics {plastics.replace('_', ', ')})",
                     "sequence": str(r.seq).upper()})
    deg = pd.read_csv(C.F_DEGRADERS, sep="\t").dropna(subset=["Sequence"])
    for d in deg.to_dict("records"):
        refs.append({"source": "degraders_list", "organism": _clean(d["Microorganism"]),
                     "taxid": int(d["Tax ID"]) if pd.notna(d["Tax ID"]) else None,
                     "accession": _clean(d["GenbankID"]) or None,
                     "record": f"{_clean(d['Enzyme'])}; plastic {_clean(d['Plastic'])}; DOI {_clean(d['DOI'])}",
                     "sequence": d["Sequence"].strip().upper(),
                     "isolation_sample_type": _clean(d["Isolation sample type"]),
                     "isolation_environment": _clean(d["Isolation environment"]),
                     "isolation_location": _clean(d["Isolation location"])})
    with gzip.open(C.F_UNIPROT, "rt") as fh:
        for r in SeqIO.parse(fh, "fasta"):
            m = re.search(r"OS=(.+?) OX=(\d+)", r.description)
            refs.append({"source": "UniProt", "organism": m.group(1), "taxid": int(m.group(2)),
                         "accession": r.id.split("|")[1], "record": r.description.split(" OS=")[0],
                         "sequence": str(r.seq).upper()})
    return refs


def _name_to_taxid():
    deg = pd.read_csv(C.F_DEGRADERS, sep="\t")
    m = deg.dropna(subset=["Tax ID"]).groupby("Microorganism")["Tax ID"].agg(lambda s: sorted({int(x) for x in s}))
    return {k.strip(): v[0] for k, v in m.items() if len(v) == 1}


def _load_records():
    with gzip.open(C.F_ASSAYS, "rt") as fh:
        return json.load(fh)


def _curation_organisms(records):
    found = defaultdict(set)
    for r in records:
        for a in r["assays"]:
            add = a["conditions"].get("additional_conditions") or {}
            for k in CURATION_KEYS:
                text = str(add.get(k) or "")
                for m in FROM_PATTERN.finditer(text):
                    if HOST_WORDS.search(text[max(0, m.start() - 40):m.start()]):
                        continue  # "expressed in X" / "recombinant X" = host, not source
                    found[r["protein_id"]].add((m.group(1).strip(), r["literature_doi"], k))
    return found


def _pazy_accessions(records):
    acc = defaultdict(set)
    for r in records:
        for a in r["assays"]:
            add = a["conditions"].get("additional_conditions") or {}
            for k in ("enzyme_accession", "publication_accession", "source_protein_accession"):
                if add.get(k):
                    acc[r["protein_id"]].add(str(add[k]))
    return acc


def genus(name):
    return str(name).split()[0].lower() if name else ""


def build_links(proteins):
    refs = _reference_sequences()
    exact = defaultdict(list)
    for ref in refs:
        exact[ref["sequence"]].append(ref)
    name_tax = _name_to_taxid()
    curation = _curation_organisms(_load_records())

    rows = []
    for pid, name, seq in zip(proteins.protein_id, proteins.protein_name, proteins.sequence):
        hits = [(ref, "exact_sequence", "identical sequence") for ref in exact.get(seq, [])]
        if not hits:
            for ref in refs:
                rs = ref["sequence"]
                if len(seq) >= MIN_OVERLAP and len(rs) >= MIN_OVERLAP and (seq in rs or rs in seq):
                    overlap = min(len(seq), len(rs)) / max(len(seq), len(rs))
                    hits.append((ref, "contained_sequence",
                                 ("PAZy sequence inside reference" if seq in rs else "reference inside PAZy sequence")
                                 + f"; overlap {100 * overlap:.0f}% of longer"))
        for ref, level, detail in hits:
            tax = ref["taxid"] or name_tax.get(ref["organism"])
            rows.append({"protein_id": pid, "protein_name": name, "organism": ref["organism"],
                         "taxonomy_id": str(tax) if tax else "",
                         "taxonomy_id_note": "" if not tax else "source record" if ref["taxid"]
                         else "organism-name match in degraders_list",
                         "evidence_level": level, "source": ref["source"], "source_record": ref["record"],
                         "accession": ref["accession"] or "", "detail": detail,
                         "isolation_sample_type": ref.get("isolation_sample_type", ""),
                         "isolation_environment": ref.get("isolation_environment", ""),
                         "isolation_location": ref.get("isolation_location", "")})
        for org, doi, key in sorted(curation.get(pid, [])):
            tax = name_tax.get(org)
            rows.append({"protein_id": pid, "protein_name": name, "organism": org,
                         "taxonomy_id": str(tax) if tax else "",
                         "taxonomy_id_note": "organism-name match in degraders_list" if tax else "",
                         "evidence_level": "pazy_curation_text", "source": "PAZy assay notes",
                         "source_record": doi, "accession": "", "detail": f"'{key}' field",
                         "isolation_sample_type": "", "isolation_environment": "", "isolation_location": ""})
    cols = ["protein_id", "protein_name", "organism", "taxonomy_id", "taxonomy_id_note", "evidence_level", "source",
            "source_record", "accession", "detail", "isolation_sample_type", "isolation_environment",
            "isolation_location"]
    return pd.DataFrame(rows, columns=cols).drop_duplicates().reset_index(drop=True)


def per_protein(proteins, links, records):
    accessions = _pazy_accessions(records)
    out = []
    for pid, name in zip(proteins.protein_id, proteins.protein_name):
        g = links[links.protein_id == pid]
        joined = lambda col, frame: "; ".join(sorted({v for v in frame[col] if v})) or NOT_DOCUMENTED
        if g.empty:
            row = {"organism": UNKNOWN, "taxonomy_id": "", "taxonomy_id_note": "", "organism_evidence": "none",
                   "evidence_sources": "", "association_type": "No organism evidence in the provided files",
                   "confidence": "none", "sources_disagree": False, "n_organism_names": 0,
                   "isolation_sample_type": NOT_DOCUMENTED, "isolation_environment": NOT_DOCUMENTED,
                   "isolation_location": NOT_DOCUMENTED, "reference_accessions": "", "evidence_detail": ""}
        else:
            level = min(g.evidence_level, key=LEVELS.index)
            best = g[g.evidence_level == level]
            orgs = sorted(set(best.organism))
            disagree = len({genus(o) for o in g.organism}) > 1
            row = {"organism": "; ".join(orgs),
                   "taxonomy_id": "; ".join(sorted({t for t in best.taxonomy_id if t})),
                   "taxonomy_id_note": "; ".join(sorted({t for t in best.taxonomy_id_note if t})),
                   "organism_evidence": level,
                   "evidence_sources": "; ".join(sorted(set(g.source))),
                   "association_type": ASSOCIATION[level],
                   "confidence": CONFIDENCE[level] + (" (sources disagree - check)" if disagree else ""),
                   "sources_disagree": disagree, "n_organism_names": len(orgs),
                   "isolation_sample_type": joined("isolation_sample_type", best),
                   "isolation_environment": joined("isolation_environment", best),
                   "isolation_location": joined("isolation_location", best),
                   "reference_accessions": "; ".join(sorted({a for a in g.accession if a})),
                   "evidence_detail": " | ".join(f"{r.source}: {r.organism} ({r.detail})" for r in g.itertuples())}
        row["uncultured_or_metagenomic"] = bool(re.search(r"uncultured|metagenom", row["organism"], re.I))
        row["accessions_in_pazy_notes"] = "; ".join(sorted(accessions.get(pid, [])))
        out.append({"protein_id": pid, "protein_name": name, **row})
    return pd.DataFrame(out)


def add_nearest_relative(org, pairs):
    """Context only: organism of the most similar protein whose organism is known."""
    known = dict(zip(org.protein_id, org.organism))
    names = dict(zip(org.protein_id, org.protein_name))
    cols = ["protein_id_a", "protein_id_b", "identity", "min_coverage"]
    sym = pd.concat([pairs[cols], pairs.rename(columns={"protein_id_a": "protein_id_b",
                                                        "protein_id_b": "protein_id_a"})[cols]])
    sym = sym[(sym.protein_id_b.map(known) != UNKNOWN) & (sym.min_coverage >= C.EDGE_MIN_COVERAGE)]
    best = sym.sort_values("identity", ascending=False).drop_duplicates("protein_id_a").set_index("protein_id_a")
    org["closest_relative_with_known_organism"] = org.protein_id.map(
        lambda p: f"{names[best.loc[p, 'protein_id_b']]} ({known[best.loc[p, 'protein_id_b']]}; "
                  f"{100 * best.loc[p, 'identity']:.0f}% identity)" if p in best.index else "")
    org["closest_relative_note"] = "Context only - a similar sequence does NOT establish the producing organism"
    return org


def run():
    C.ensure_dirs()
    proteins = preprocess.load_proteins()
    links = build_links(proteins)
    links.to_csv(C.ORGANISMS / "organism_links.csv", index=False)
    org = per_protein(proteins, links, _load_records())
    org = add_nearest_relative(org, pd.read_csv(C.F_PAIRS))
    org.to_csv(C.ORGANISMS / "protein_organisms.csv", index=False)
    summary = org.organism_evidence.value_counts().rename_axis("evidence").reset_index(name="proteins")
    summary.to_csv(C.ORGANISMS / "organism_evidence_summary.csv", index=False)
    print(f"[stage 4] organism known for {int((org.organism != UNKNOWN).sum())}/{len(org)} proteins "
          f"({links.organism.nunique()} organism names, {len(links)} source links)")
    print(summary.to_string(index=False))
    print("with Tax ID:", int((org.taxonomy_id != "").sum()), "| sources disagree:", int(org.sources_disagree.sum()),
          "| uncultured/metagenomic:", int(org.uncultured_or_metagenomic.sum()),
          "| isolation environment documented:", int((org.isolation_environment != NOT_DOCUMENTED).sum()))
    return org
