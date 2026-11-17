"""Sequence Laboratory: query validation and matching."""

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pet_explorer import config as C
from pet_explorer.sequence_matching import SequenceInputError

from ..services import matching, store

router = APIRouter()

# Real reference sequences offered as examples (looked up by name, never typed in).
EXAMPLE_NAMES = ["ISPETase", "LCC", "TfCut2", "PHL7"]


class MatchRequest(BaseModel):
    sequence: str = Field(..., max_length=20000)
    top_n: int = Field(5, ge=1, le=10)


# Unrelated-protein example, read from the shipped sample dataset (not part of the reference set).
CONTROL_EXAMPLES = [("02_Positive_vs_Unrelated.csv", "Human_HBB", "Human haemoglobin (HBB)")]


@router.get("/sequence/examples")
def examples():
    p = store.proteins()
    out = []
    for name in EXAMPLE_NAMES:
        r = p[p.protein_name == name]
        if len(r):
            r = r.iloc[0]
            out.append({"protein_id": int(r.protein_id), "protein_name": r.protein_name,
                        "subcluster": r.subcluster, "length": int(r.sequence_length), "kind": "reference",
                        "fasta": f">{r.protein_id} {r.protein_name} | PAZy reference sequence\n{r.sequence}"})
    for fname, pid, label in CONTROL_EXAMPLES:
        path = C.DATA / "samples" / fname
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype=str)
        r = df[df.protein_id == pid]
        if len(r):
            seq = r.sequence.iloc[0].strip()
            out.append({"protein_id": pid, "protein_name": label, "subcluster": None, "length": len(seq),
                        "kind": "control",
                        "fasta": f">{pid} {label} | unrelated protein example (not a PET reference)\n{seq}"})
    return out


@router.get("/sequence/method")
def method():
    return matching.method()


@router.post("/sequence/match")
def match(req: MatchRequest):
    try:
        return matching.search(req.sequence, top_n=req.top_n)
    except SequenceInputError as e:
        raise HTTPException(422, str(e))
