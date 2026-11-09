"""Sequence profiles and bulk analysis.

Files arrive base64-encoded inside JSON (no multipart parsing needed), are read
in memory by pet_explorer.batch and are never stored on disk. Activity
predictions go through services.prediction, which reports "Prediction not
available" while no validated model exists.
"""

import base64
import binascii
import io
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from pet_explorer import batch as B
from pet_explorer import config as C
from pet_explorer.sequence_matching import SequenceInputError, parse_query

from ..services import batch_jobs, matching, prediction, store

router = APIRouter()

MAX_B64 = (B.MAX_FILE_BYTES * 4) // 3 + 16


class ProfileRequest(BaseModel):
    sequence: str = Field(..., max_length=20000)


class UploadRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    content_base64: str = Field(..., max_length=MAX_B64)
    mapping: Optional[Dict[str, Optional[str]]] = None
    include_rows: Optional[List[int]] = None   # e.g. the PDF candidates the user confirmed


def _decode(req: UploadRequest) -> bytes:
    try:
        return base64.b64decode(req.content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "The upload is not valid base64.") from None


def _parse(req: UploadRequest) -> dict:
    try:
        parsed = B.parse_upload(req.filename, _decode(req), req.mapping)
    except B.UploadError as e:
        raise HTTPException(422, str(e)) from None
    if req.include_rows is not None:
        keep = set(req.include_rows)
        parsed["records"] = B.validate([r for r in parsed["records"] if r.row in keep])
        if not parsed["records"]:
            raise HTTPException(422, "No records were selected.")
    return parsed


def _counts(records) -> dict:
    out = {"total": len(records)}
    for s in ("valid", "invalid", "duplicate"):
        out[s] = sum(r.status == s for r in records)
    return out


def _hit(h, full: bool) -> dict:
    card = store.protein_card(h.protein_id)
    out = {
        "protein_id": h.protein_id, "protein_name": h.protein_name,
        "identity": round(h.identity, 4), "query_coverage": round(h.query_coverage, 4),
        "target_coverage": round(h.target_coverage, 4), "normalised_score": round(h.normalised_score, 4),
        "shuffled_z": round(h.shuffled_z, 1), "interpretation": h.interpretation,
        "query_range": list(h.query_range), "target_range": list(h.target_range),
        # experimental evidence belongs to the reference protein, not to the query
        "reference": {k: card[k] for k in ("subcluster", "pet_label", "label_confidence", "n_pet_assays",
                                           "n_positive_assays", "n_publications", "temperatures_with_activity_c",
                                           "organism")},
    }
    if full:
        out.update(aligned_query=h.aligned_query, aligned_target=h.aligned_target)
    return out


def _analyse(rec: B.Record) -> dict:
    a = B.analyse(rec.sequence, matching.matcher())
    hits = [_hit(h, i == 0) for i, h in enumerate(a.pop("hits"))]
    return {**a, "status": "analysed", "hits": hits, "prediction": prediction.for_sequence()}


@router.post("/sequence/profile")
def profile(req: ProfileRequest):
    """Composition, physicochemical properties, motifs and the prediction status of one sequence."""
    try:
        header, seq = parse_query(req.sequence)
    except SequenceInputError as e:
        raise HTTPException(422, str(e)) from None
    return {"header": header, **B.profile(seq), "prediction": prediction.for_sequence()}


@router.get("/batch/limits")
def limits():
    return {"max_file_mb": B.MAX_FILE_BYTES // (1024 * 1024), "max_records": B.MAX_RECORDS,
            "min_length": C.MIN_QUERY_LEN, "max_length": C.MAX_QUERY_LEN,
            "formats": sorted(set(B.FORMATS)), "prediction": prediction.status()}


@router.post("/batch/parse")
def parse(req: UploadRequest):
    """Preview: how the file was read and which records are valid. Nothing is analysed yet."""
    p = _parse(req)
    return {**{k: v for k, v in p.items() if k != "records"},
            "records": [r.summary() for r in p["records"]], "counts": _counts(p["records"])}


@router.post("/batch/jobs")
def start(req: UploadRequest):
    p = _parse(req)
    counts = _counts(p["records"])
    if not counts["valid"]:
        raise HTTPException(422, "None of the records holds a valid protein sequence.")
    job = batch_jobs.submit(p["records"], {"filename": req.filename, "format": p["format"], "counts": counts},
                            _analyse)
    return job.view()


@router.get("/batch/jobs/{job_id}")
def poll(job_id: str, since: int = Query(0, ge=0)):
    job = batch_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "This batch has expired or does not exist. Upload the file again.")
    return job.view(since)


@router.delete("/batch/jobs/{job_id}")
def cancel(job_id: str):
    if not batch_jobs.delete(job_id):
        raise HTTPException(404, "Unknown batch.")
    return {"deleted": True}


def _safe(v):
    """Neutralise spreadsheet formula injection in user-supplied text cells."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def export_frame(results: List[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        top = (r.get("hits") or [None])[0]
        phys = r.get("physicochemical") or {}
        mot = r.get("motifs") or {}
        pred = r.get("prediction") or {}
        cond = pred.get("condition") or {}
        rows.append({
            "record": r["row"], "source": r.get("source"), "protein_id": r.get("protein_id"),
            "organism": r.get("organism"), "status": r.get("status"),
            "errors": "; ".join(r.get("errors") or []), "warnings": "; ".join(r.get("warnings") or []),
            "duplicate_of_record": r.get("duplicate_of"), "length_aa": r.get("length"),
            **{k: phys.get(k) for k in ("molecular_weight_kda", "isoelectric_point", "gravy", "aromaticity",
                                        "instability_index")},
            "gxsxg_count": mot.get("count"), "gxsxg_positions": "; ".join(map(str, mot.get("positions") or [])),
            "nearest_reference": top and top["protein_name"],
            "identity_pct": top and round(100 * top["identity"], 1),
            "query_coverage_pct": top and round(100 * top["query_coverage"], 1),
            "reference_coverage_pct": top and round(100 * top["target_coverage"], 1),
            "normalised_score": top and top["normalised_score"], "shuffled_z": top and top["shuffled_z"],
            "similarity_interpretation": top and top["interpretation"],
            "reference_pet_evidence": top and (f"{top['reference']['n_positive_assays']} positive of "
                                               f"{top['reference']['n_pet_assays']} PET assays "
                                               f"({top['reference']['n_publications']} publication(s))"),
            "evidence_status": r.get("evidence_status"),
            "prediction_status": pred.get("label"), "prediction_score": pred.get("score"),
            "prediction_condition": f"{cond['target']}; {cond['substrate']}; {cond['protocol']}" if cond else None,
            "prediction_note": pred.get("reason"),
        })
    return pd.DataFrame(rows).map(_safe)


@router.get("/batch/jobs/{job_id}/export")
def export(job_id: str, format: str = Query("csv", pattern="^(csv|xlsx)$")):
    job = batch_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "This batch has expired or does not exist.")
    df = export_frame(job.results)
    stem = "pet_explorer_batch"
    if format == "csv":
        body = io.BytesIO(df.to_csv(index=False).encode("utf-8-sig"))
        media, name = "text/csv", f"{stem}.csv"
    else:
        body = io.BytesIO()
        with pd.ExcelWriter(body, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="results")
            pd.DataFrame([{"field": k, "value": v} for k, v in {
                "file": job.meta.get("filename"), "records": len(job.results),
                "similarity method": matching.method()["algorithm"] + ", " + matching.method()["matrix"],
                "prediction": prediction.status()["reason"],
                "note": "Sequence similarity is not experimental evidence of PET activity.",
            }.items()]).to_excel(xw, index=False, sheet_name="about")
        body.seek(0)
        media, name = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{stem}.xlsx"
    return StreamingResponse(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})
