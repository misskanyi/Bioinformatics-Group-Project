"""Biological interpretation - domain annotation and literature comparison.

Domains: every sequence is looked up in UniParc (UniProt's archive of all
unique protein sequences) by the MD5 checksum of its exact sequence. UniParc
stores InterPro's pre-computed member-database matches (Pfam, Gene3D,
SUPERFAMILY, PANTHER...) for each sequence, so no sequence is submitted
anywhere and no account or e-mail is needed. Sequences absent from UniParc
(e.g. unpublished variants) are reported as "not in UniParc", never guessed.
The result is cached in outputs/explorer/annotation/ so the notebook runs
offline; pass refresh=True to query again.

Literature: well-studied PET hydrolases are located in our groups and their
published properties are set next to the computed cluster and motif.
"""

import hashlib
import json
import time
import urllib.parse
import urllib.request

import pandas as pd

from . import config as C, plots

UNIPARC = "https://rest.uniprot.org/uniparc/search"
F_FEATURES = C.ANNOTATION / "uniparc_domain_matches.csv"

# name in PAZy -> published facts (source in brackets)
REFERENCE_ENZYMES = {
    "ISPETase": "Ideonella sakaiensis PETase, from a bacterium living on PET; mesophilic (~30 °C) "
                "[Yoshida et al. 2016, Science]. 'Type IIb' PETase [Joo et al. 2018, Nat Commun]. Trp next to "
                "the catalytic Ser; W159H makes the active site cutinase-like [Austin et al. 2018, PNAS].",
    "LCC": "Leaf-branch compost cutinase, metagenome [Sulaiman et al. 2012]. Thermophilic; engineered variant "
           "ICCG depolymerised 90% of PET in 10 h at 72 °C [Tournier et al. 2020, Nature]. 'Type I' [Joo et al. 2018].",
    "TfCut2": "Thermobifida fusca cutinase, thermophilic actinomycete [Roth et al. 2014]. 'Type I' [Joo et al. 2018].",
    "TfH": "Thermobifida fusca hydrolase, one of the first PET hydrolases described [Müller et al. 2005].",
    "Cut190": "Saccharomonospora viridis cutinase; Ca2+-dependent thermostability [Kawai et al. 2014].",
    "Tcur_1278": "Thermomonospora curvata cutinase, thermophilic actinomycete [Wei et al. 2014].",
    "BhrPETase": "Bacterium HR29 PETase, close LCC homolog, highly thermostable [Xi et al. 2021].",
    "PE-H": "Pseudomonas aestusnigri, marine; 'Type IIa' PETase [Bollinger et al. 2020].",
    "PET2": "Metagenome-derived PET hydrolase [Danso et al. 2018].",
    "HiC": "Humicola insolens cutinase - a FUNGAL cutinase, PET hydrolysis at ~70 °C [Ronkvist et al. 2009].",
}


def md5(seq):
    return hashlib.md5(seq.encode()).hexdigest().upper()


def fetch_uniparc(proteins, batch=25, pause=0.5):
    """One row per (protein, member-database match, location)."""
    by_md5 = {}
    for pid, seq in zip(proteins.protein_id, proteins.sequence):
        by_md5.setdefault(md5(seq), []).append(pid)
    keys = list(by_md5)
    rows, found = [], set()
    for i in range(0, len(keys), batch):
        q = " OR ".join(f"checksum:{k}" for k in keys[i:i + batch])
        url = f"{UNIPARC}?{urllib.parse.urlencode({'query': q, 'format': 'json', 'size': 500})}"
        with urllib.request.urlopen(url, timeout=120) as r:
            results = json.load(r)["results"]
        for e in results:
            m = e["sequence"]["md5"]
            if m not in by_md5:
                continue
            found.add(m)
            for f in e.get("sequenceFeatures", []):
                ipr = f.get("interproGroup") or {}
                for loc in f.get("locations", []) or [{}]:
                    for pid in by_md5[m]:
                        rows.append({"protein_id": pid, "uniparc_id": e["uniParcId"], "database": f.get("database"),
                                     "database_id": f.get("databaseId"), "interpro_id": ipr.get("id"),
                                     "interpro_name": ipr.get("name"), "start": loc.get("start"),
                                     "end": loc.get("end")})
        time.sleep(pause)
    missing = [{"protein_id": pid, "uniparc_id": None, "database": "not in UniParc"}
               for m in set(keys) - found for pid in by_md5[m]]
    return pd.DataFrame(rows + missing)


def load_features(proteins, refresh=False):
    if refresh or not F_FEATURES.exists():
        fetch_uniparc(proteins).to_csv(F_FEATURES, index=False)
    return pd.read_csv(F_FEATURES)


def pfam_per_protein(features):
    pf = features[features.database == "Pfam"]
    return (pf.assign(label=pf.database_id + " " + pf.interpro_name.fillna(""))
            .groupby("protein_id").label.agg(lambda s: "; ".join(sorted(set(s)))))


def domain_summary(features, assign):
    """Per group: UniParc coverage and the Pfam families found."""
    pfam = pfam_per_protein(features)
    in_uniparc = set(features.loc[features.uniparc_id.notna(), "protein_id"])
    rows = []
    for g, members in assign.groupby("subcluster").protein_id:
        known = [p for p in members if p in in_uniparc]
        labels = pfam.reindex(known).dropna().str.split("; ").explode().value_counts()
        rows.append({"subcluster": g, "n_proteins": len(members), "n_in_uniparc": len(known),
                     "n_with_pfam": int(pfam.reindex(known).notna().sum()),
                     "pfam_families": "; ".join(f"{k} ({v})" for k, v in labels.items()) or "none"})
    return pd.DataFrame(rows).sort_values("subcluster", key=lambda s: s.map(plots.group_key))


def literature_table(proteins, assign, feats, features, centrality):
    pfam = pfam_per_protein(features)
    d = (proteins[["protein_id", "protein_name", "sequence_length"]]
         .merge(assign[["protein_id", "subcluster"]], on="protein_id")
         .merge(feats[["protein_id", "gxsxg_variants"]], on="protein_id")
         .merge(centrality[["protein_id", "degree"]], on="protein_id", how="left"))
    rows = []
    for name, note in REFERENCE_ENZYMES.items():
        hit = d[d.protein_name.str.lower() == name.lower()]
        if hit.empty:
            continue
        r = hit.iloc[0]
        rows.append({"enzyme": r.protein_name, "subcluster": r.subcluster, "length_aa": r.sequence_length,
                     "gxsxg_motifs": r.gxsxg_variants, "pfam": pfam.get(r.protein_id, "not in UniParc / none"),
                     "ssn_degree": r.degree, "published_properties": note})
    return pd.DataFrame(rows)


def run(refresh=False):
    C.ensure_dirs()
    proteins = pd.read_csv(C.F_PROTEINS)
    assign = pd.read_csv(C.CLUSTERING / "cluster_assignments.csv")
    feats = pd.read_csv(C.CLUSTERING / "sequence_features.csv")
    cent = pd.read_csv(C.NETWORK / "centrality.csv")
    features = load_features(proteins, refresh)
    summary = domain_summary(features, assign)
    summary.to_csv(C.ANNOTATION / "domains_by_group.csv", index=False)
    lit = literature_table(proteins, assign, feats, features, cent)
    lit.to_csv(C.ANNOTATION / "literature_comparison.csv", index=False)
    print(f"[annotation] {features.loc[features.uniparc_id.notna(), 'protein_id'].nunique()} / {len(proteins)} "
          f"sequences found in UniParc")
    print(summary.to_string(index=False))
    print(lit.drop(columns="published_properties").to_string(index=False))
    return summary, lit
