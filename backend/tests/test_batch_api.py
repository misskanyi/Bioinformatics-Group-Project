"""Bulk-analysis and profile endpoints.

    .venv/bin/pytest backend/tests -q        # from the repository root
"""

import base64
import io
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from pet_explorer import config as C


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def proteins():
    return pd.read_csv(C.F_PROTEINS)


def body(name, text, **kw):
    return {"filename": name, "content_base64": base64.b64encode(text.encode()).decode(), **kw}


def run(client, payload):
    job = client.post("/api/batch/jobs", json=payload)
    assert job.status_code == 200, job.text
    jid = job.json()["job_id"]
    for _ in range(300):
        v = client.get(f"/api/batch/jobs/{jid}").json()
        if v["state"] == "done":
            return jid, v
        time.sleep(0.1)
    raise AssertionError("batch did not finish")


def test_profile_reports_no_prediction(client, proteins):
    r = client.post("/api/sequence/profile", json={"sequence": proteins.sequence[0]}).json()
    assert r["length"] == len(proteins.sequence[0])
    assert r["prediction"]["status"] == "not_available" and r["prediction"]["score"] is None
    assert r["prediction"]["condition"]["temperature_c"] == 60


def test_prediction_gate_follows_permutation_test(client):
    perm = pd.read_csv(C.PREDICTION / "permutation_test.csv").iloc[0]
    s = client.get("/api/batch/limits").json()["prediction"]
    assert s["permutation_p"] == perm.empirical_p
    assert s["available"] is False   # no persisted model, and the best one does not beat its null


def test_batch_end_to_end(client, proteins):
    isp = proteins.loc[proteins.protein_name == "ISPETase", "sequence"].iloc[0]
    fasta = f">exact\n{isp}\n>fragment\n{isp[30:230]}\n>dna\n{'ATGC' * 15}\n>copy\n{isp}\n"
    jid, v = run(client, body("q.fasta", fasta))
    rows = {r["protein_id"]: r for r in v["results"]}
    assert v["total"] == v["done"] == 4
    assert rows["exact"]["evidence_status"] == "experimental"
    top = rows["fragment"]["hits"][0]
    assert top["identity"] > 0.95 and top["query_coverage"] == 1   # the IsPETase family
    assert rows["fragment"]["evidence_status"] == "similarity"     # a fragment is not the characterised protein
    assert rows["dna"]["status"] == "invalid" and "DNA" in rows["dna"]["errors"][0]
    assert rows["copy"]["status"] == "duplicate" and rows["copy"]["duplicate_of"] == 1
    for r in v["results"]:
        assert "probability" not in r
        if r["status"] == "analysed":
            assert r["prediction"]["score"] is None

    # incremental polling returns only new rows
    assert client.get(f"/api/batch/jobs/{jid}?since=3").json()["results"][0]["protein_id"] == "copy"

    csv = client.get(f"/api/batch/jobs/{jid}/export?format=csv")
    df = pd.read_csv(io.StringIO(csv.content.decode("utf-8-sig")))
    assert len(df) == 4 and (df.prediction_status.dropna() == "Prediction not available").all()
    xlsx = client.get(f"/api/batch/jobs/{jid}/export?format=xlsx")
    assert pd.read_excel(io.BytesIO(xlsx.content), sheet_name="results").shape[0] == 4

    assert client.delete(f"/api/batch/jobs/{jid}").json()["deleted"]
    assert client.get(f"/api/batch/jobs/{jid}").status_code == 404


def test_export_neutralises_formulas(client, proteins):
    csv = f"id,sequence\n=1+1,{proteins.sequence[3]}\n"
    jid, _ = run(client, body("t.csv", csv))
    out = client.get(f"/api/batch/jobs/{jid}/export?format=csv").content.decode("utf-8-sig")
    assert "'=1+1" in out


def test_parse_preview_and_confirmation(client, proteins):
    fasta = "".join(f">p{i}\n{s}\n" for i, s in enumerate(proteins.sequence[:3]))
    p = client.post("/api/batch/parse", json=body("q.fasta", fasta)).json()
    assert p["counts"] == {"total": 3, "valid": 3, "invalid": 0, "duplicate": 0}
    _, v = run(client, body("q.fasta", fasta, include_rows=[2]))
    assert [r["protein_id"] for r in v["results"]] == ["p1"]


@pytest.mark.parametrize("payload,status", [
    ({"filename": "a.exe", "content_base64": "eA=="}, 422),
    ({"filename": "a.fasta", "content_base64": "not base64!"}, 422),
    ({"filename": "a.fasta", "content_base64": base64.b64encode(b">x\nATGCATGCATGCATGCATGCATGCATGCATGC").decode()}, 422),
])
def test_bad_uploads(client, payload, status):
    assert client.post("/api/batch/jobs", json=payload).status_code == status
