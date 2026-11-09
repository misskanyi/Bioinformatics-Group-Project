"""Bulk protein-sequence analysis.

Turns an uploaded file into records, validates every record on its own (one
bad row never fails the batch) and profiles each valid sequence with the same
functions used for the curated set: features.physicochemical / composition /
motifs and the reference SequenceMatcher.

Uploaded content is only ever read as data and never written to disk:
* CSV / TSV  - pandas C parser, every cell read as a string
* Excel      - .xlsx only, openpyxl read-only mode (formulas are not evaluated,
               macros are never loaded; .xlsm / .xls are rejected)
* FASTA/TXT  - plain text
* PDF        - text layer only, via pypdf (no rendering, scripts or embedded
               files). Candidate sequences are heuristic and must be confirmed.
"""

import io
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from . import config as C, features
from .sequence_matching import SequenceInputError, SequenceMatcher, parse_query

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 500
MAX_TABLE_ROWS = 5000

FORMATS = {
    ".csv": "csv", ".tsv": "tsv", ".xlsx": "xlsx",
    ".fasta": "fasta", ".fa": "fasta", ".faa": "fasta", ".fas": "fasta",
    ".txt": "txt", ".pdf": "pdf",
}

_AA_TOKEN = re.compile(r"[ACDEFGHIKLMNPQRSTVWY]+")
_TOKEN = re.compile(r"[A-Za-z0-9_.:|\-]{2,}")
_OS = re.compile(r"\bOS=(.+?)(?:\s+[A-Z]{2}=|$)")        # UniProt FASTA header
_BRACKET = re.compile(r"\[([A-Z][^\[\]]+)\]\s*$")        # NCBI FASTA header


class UploadError(ValueError):
    """The file as a whole cannot be read (wrong type, too large, unreadable)."""


@dataclass
class Record:
    row: int                      # 1-based position in the source (table row / FASTA record / PDF candidate)
    protein_id: str
    raw_sequence: str
    organism: Optional[str] = None
    source: str = ""              # human-readable origin, e.g. "line 12" or "page 3"
    sequence: Optional[str] = None
    status: str = "pending"       # valid | invalid | duplicate
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duplicate_of: Optional[int] = None

    def summary(self) -> dict:
        return {"row": self.row, "protein_id": self.protein_id, "organism": self.organism, "source": self.source,
                "length": len(self.sequence) if self.sequence else None, "status": self.status,
                "errors": self.errors, "warnings": self.warnings, "duplicate_of": self.duplicate_of,
                "preview": (self.sequence or self.raw_sequence)[:60]}


# ------------------------------------------------------------------ reading

def file_format(filename: str) -> str:
    name = (filename or "").lower()
    for ext, fmt in FORMATS.items():
        if name.endswith(ext):
            return fmt
    if name.endswith((".xls", ".xlsm")):
        raise UploadError("Only .xlsx workbooks are accepted (.xls and macro-enabled .xlsm are not).")
    raise UploadError("Unsupported file type. Use CSV, TSV, Excel (.xlsx), FASTA (.fasta/.fa), TXT or PDF.")


def _text(data: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UploadError("The file is not readable as text.")


def parse_fasta(text: str) -> List[Record]:
    out, header, lines, start = [], None, [], 0
    rows = text.splitlines()

    def flush():
        if header is None:
            return
        name = header.split()[0] if header.split() else ""
        m = _OS.search(header) or _BRACKET.search(header)
        out.append(Record(row=len(out) + 1, protein_id=name, raw_sequence="".join(lines),
                          organism=m.group(1).strip() if m else None, source=f"line {start}"))

    for i, ln in enumerate(rows, 1):
        s = ln.strip()
        if s.startswith(">"):
            flush()
            header, lines, start = s[1:].strip(), [], i
        elif s and header is not None:
            lines.append(s)
        elif s and header is None:
            raise UploadError(f"Line {i} has sequence text before the first FASTA header ('>').")
    flush()
    return out


def parse_text(text: str) -> List[Record]:
    """FASTA if it has headers; otherwise blocks separated by blank lines, each either
    one (possibly wrapped) sequence or lines of `identifier<separator>sequence`."""
    if any(ln.lstrip().startswith(">") for ln in text.splitlines()):
        return parse_fasta(text)
    out = []
    blocks, cur, cur_start = [], [], 0
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.strip():
            if not cur:
                cur_start = i
            cur.append(ln.strip())
        elif cur:
            blocks.append((cur_start, cur))
            cur = []
    if cur:
        blocks.append((cur_start, cur))
    for start, block in blocks:
        split = [re.split(r"[\s,;\t]+", ln, maxsplit=1) for ln in block]
        if all(len(p) == 2 and re.fullmatch(r"[A-Za-z*\s]{10,}", p[1]) for p in split):
            for j, (pid, seq) in enumerate(split):
                out.append(Record(row=len(out) + 1, protein_id=pid, raw_sequence=seq, source=f"line {start + j}"))
        else:
            out.append(Record(row=len(out) + 1, protein_id="", raw_sequence="".join(block), source=f"line {start}"))
    return out


def read_table(data: bytes, fmt: str) -> pd.DataFrame:
    try:
        if fmt == "xlsx":
            df = pd.read_excel(io.BytesIO(data), dtype=str, engine="openpyxl", nrows=MAX_TABLE_ROWS + 1)
        else:
            df = pd.read_csv(io.StringIO(_text(data)), dtype=str, sep="\t" if fmt == "tsv" else None,
                             engine="python", nrows=MAX_TABLE_ROWS + 1)
    except UploadError:
        raise
    except Exception as e:  # malformed workbook / CSV
        raise UploadError(f"The table could not be read: {e}") from None
    if len(df) > MAX_TABLE_ROWS:
        raise UploadError(f"The table has more than {MAX_TABLE_ROWS} rows.")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _protein_like(values: pd.Series) -> float:
    v = values.dropna().astype(str).str.replace(r"\s", "", regex=True).str.upper()
    if not len(v):
        return 0.0
    return float(v.str.fullmatch(r"[A-Z*]{30,}").mean())


def guess_mapping(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    cols = list(df.columns)

    def by_name(pattern):
        return next((c for c in cols if re.search(pattern, c, re.I)), None)

    seq = by_name(r"sequence|^seq|aa_?seq|amino")
    if seq is None or _protein_like(df[seq]) < 0.5:
        scored = sorted(((_protein_like(df[c]), c) for c in cols), reverse=True)
        seq = scored[0][1] if scored and scored[0][0] >= 0.5 else seq
    pid = by_name(r"^(protein_?)?id$|accession|identifier|^name$|protein_?name|entry")
    org = by_name(r"organism|species|source_?organism|host|taxon")
    return {"protein_id": pid if pid != seq else None, "sequence": seq, "organism": org if org not in (seq, pid) else None}


def table_records(df: pd.DataFrame, mapping: Dict[str, Optional[str]]) -> List[Record]:
    seq_col = mapping.get("sequence")
    if not seq_col or seq_col not in df.columns:
        raise UploadError("Choose which column holds the amino-acid sequences.")
    for k in ("protein_id", "organism"):
        if mapping.get(k) and mapping[k] not in df.columns:
            raise UploadError(f"Column '{mapping[k]}' does not exist.")

    def cell(r, col):
        if not col:
            return None
        v = r[col]
        return None if pd.isna(v) or not str(v).strip() else str(v).strip()

    out = []
    for i, (_, r) in enumerate(df.iterrows()):
        out.append(Record(row=i + 1, protein_id=cell(r, mapping.get("protein_id")) or "",
                          raw_sequence=cell(r, seq_col) or "", organism=cell(r, mapping.get("organism")),
                          source=f"row {i + 2}"))   # +1 header, +1 for 1-based spreadsheet rows
    return out


def parse_pdf(data: bytes) -> List[Record]:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - dependency listed in backend/requirements.txt
        raise UploadError("PDF support needs the 'pypdf' package on the server.") from None
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UploadError("Encrypted PDFs are not supported.")
        pages = [(n, page.extract_text() or "") for n, page in enumerate(reader.pages, 1)]
    except UploadError:
        raise
    except Exception as e:
        raise UploadError(f"The PDF could not be read: {e}") from None
    if not any(t.strip() for _, t in pages):
        raise UploadError("No text layer found. Scanned (image-only) PDFs cannot be read; export the table as CSV instead.")

    out = []

    def flush(cur):
        if cur and len(cur["seq"]) >= C.MIN_QUERY_LEN:
            out.append(Record(row=len(out) + 1, protein_id=cur["id"], raw_sequence=cur["seq"], source=f"page {cur['page']}",
                              warnings=["Extracted from PDF text: check that line breaks did not merge or split sequences."]))

    for n, text in pages:
        cur = None
        for ln in text.splitlines():
            toks = ln.split()
            k = len(toks)               # toks[k:] = trailing run of amino-acid-only tokens
            while k and _AA_TOKEN.fullmatch(toks[k - 1]):
                k -= 1
            if k == 0 and len(toks) > 1 and len(toks[0]) < 10:
                k = 1                   # short upper-case identifier such as "LCC" before the sequence
            run = toks[k:]
            # real sequences have long unbroken stretches; upper-case prose does not
            longest = max((len(t) for t in run), default=0)
            if k == 0 and cur is not None and longest >= 10:
                cur["seq"] += "".join(run)   # wrapped continuation of the previous table cell
                continue
            flush(cur)
            cur = None
            if longest >= 20:
                ids = [t for t in toks[:k] if _TOKEN.fullmatch(t)]
                cur = {"id": ids[-1] if ids else "", "seq": "".join(run), "page": n}
        flush(cur)
    return out


def parse_upload(filename: str, data: bytes, mapping: Optional[Dict[str, Optional[str]]] = None) -> dict:
    """Read a file into unvalidated records. Tabular formats also return their columns and mapping."""
    if len(data) > MAX_FILE_BYTES:
        raise UploadError(f"File is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise UploadError("The file is empty.")
    fmt = file_format(filename)
    extra: dict = {}
    if fmt in ("csv", "tsv", "xlsx"):
        df = read_table(data, fmt)
        used = mapping if mapping is not None else guess_mapping(df)
        records = table_records(df, used)
        extra = {"columns": list(df.columns), "mapping": used,
                 "suggested_mapping": guess_mapping(df),
                 "preview_rows": df.head(5).fillna("").astype(str).apply(lambda s: s.str.slice(0, 80)).to_dict("records")}
    elif fmt == "pdf":
        records = parse_pdf(data)
    elif fmt == "fasta":
        records = parse_fasta(_text(data))
    else:
        records = parse_text(_text(data))
    if not records:
        raise UploadError("No sequence records were found in the file.")
    if len(records) > MAX_RECORDS:
        raise UploadError(f"The file holds {len(records)} records; the limit per batch is {MAX_RECORDS}.")
    validate(records)
    return {"format": fmt, "records": records, "requires_confirmation": fmt == "pdf", **extra}


# ------------------------------------------------------------------ validation

def validate(records: List[Record]) -> List[Record]:
    """Per-record checks with the same rules as single-sequence input; duplicates keep their own row."""
    seen_seq: Dict[str, int] = {}
    seen_id: Dict[str, int] = {}
    for r in records:
        r.errors, r.sequence, r.duplicate_of = [], None, None
        if not r.raw_sequence.strip():
            r.status, r.errors = "invalid", ["Missing sequence."]
        else:
            try:
                _, r.sequence = parse_query(r.raw_sequence)
                r.status = "valid"
            except SequenceInputError as e:
                r.status, r.errors = "invalid", [str(e)]
        if not r.protein_id:
            r.protein_id = f"row_{r.row}"
            r.warnings.append("No identifier supplied; the row number is used instead.")
        if r.protein_id in seen_id:
            r.warnings.append(f"Identifier also used by record {seen_id[r.protein_id]}.")
        else:
            seen_id[r.protein_id] = r.row
        if r.status == "valid":
            if r.sequence in seen_seq:
                r.status, r.duplicate_of = "duplicate", seen_seq[r.sequence]
            else:
                seen_seq[r.sequence] = r.row
    return records


# ------------------------------------------------------------------ analysis

def profile(sequence: str) -> dict:
    """Length, composition, ProtParam properties and G-x-S-x-G motifs for one validated sequence."""
    one = pd.DataFrame({"protein_id": [0], "sequence": [sequence]})
    phys = features.physicochemical(one).iloc[0]
    comp = features.composition(one).iloc[0]
    mot = features.motifs(one).iloc[0]
    positions = [int(p) for p in str(mot.gxsxg_positions).split("; ") if p]
    return {
        "length": len(sequence),
        "composition": {a: round(float(comp[f"aa_{a}"]), 2) for a in C.STANDARD_AA},
        "physicochemical": {
            "molecular_weight_kda": round(float(phys.molecular_weight_kda), 2),
            "isoelectric_point": round(float(phys.isoelectric_point), 2),
            "gravy": round(float(phys.gravy), 3),
            "aromaticity": round(float(phys.aromaticity), 3),
            "instability_index": round(float(phys.instability_index), 1),
            "helix_prone_fraction": round(float(phys.helix_prone_fraction), 3),
            "turn_prone_fraction": round(float(phys.turn_prone_fraction), 3),
            "sheet_prone_fraction": round(float(phys.sheet_prone_fraction), 3),
        },
        "motifs": {
            "name": "G-x-S-x-G (catalytic-serine motif of alpha/beta-hydrolases)",
            "count": int(mot.gxsxg_count),
            "variants": [v for v in str(mot.gxsxg_variants).split("; ") if v],
            "positions": positions,
        },
    }


def evidence_status(top) -> str:
    """Which kind of evidence the nearest match provides for this query."""
    if top is None:
        return "unknown"
    if top.identity == 1 and top.query_coverage == 1 and top.target_coverage == 1:
        return "experimental"          # the query IS a characterised reference protein
    if top.interpretation != C.NO_MATCH_BAND:
        return "similarity"
    return "unknown"


def analyse(sequence: str, matcher: SequenceMatcher, top_n: int = 3, n_shuffles: int = 10) -> dict:
    _, _, hits = matcher.search(sequence, top_n=top_n, n_shuffles=n_shuffles)
    return {**profile(sequence), "hits": hits, "evidence_status": evidence_status(hits[0] if hits else None)}
