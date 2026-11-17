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


# ------------------------------------------------------------------ sample datasets & evidence assessment

def _sample_run(client, s, filename=None, text=None):
    raw = text if text is not None else client.get(s["download_url"]).content.decode("utf-8-sig")
    _, v = run(client, body(filename or s["filename"], raw))
    return v


def test_samples_listed_and_downloadable(client):
    s = client.get("/api/batch/samples").json()
    assert [x["n_proteins"] for x in s] == [3, 3, 3]
    assert s[0]["proteins"] == ["IsPETase", "LCC", "TfCut2"]
    assert "Human_HBB" in s[1]["proteins"] and "Human_HBB" in s[2]["proteins"]
    for x in s:
        r = client.get(x["download_url"])
        assert r.status_code == 200 and r.text.startswith("protein_id,sequence")
    assert client.get("/api/batch/samples/nope/download").status_code == 404


def test_samples_analyse_with_calculated_assessments(client):
    s = {x["id"]: x for x in client.get("/api/batch/samples").json()}
    for sid in s:
        v = _sample_run(client, s[sid])
        assert v["done"] == v["total"] == 3
        for r in v["results"]:
            assert r["status"] == "analysed"
            a = r["assessment"]
            assert a["category"] in ("green", "yellow", "red", "insufficient")
            assert a["metrics"]["identity"] == r["hits"][0]["identity"]   # computed from this row's alignment
    known = {r["protein_id"]: r["assessment"] for r in _sample_run(client, s["known-pet-enzymes"])["results"]}
    assert all(a["category"] == "green" and a["known_reference"] for a in known.values())
    low = {r["protein_id"]: r["assessment"] for r in _sample_run(client, s["low-evidence-controls"])["results"]}
    assert all(a["category"] in ("red", "insufficient") and not a["known_reference"] for a in low.values())
    assert low["Synthetic_Control_A"]["tandem_repeat_period"] == 10


def test_names_do_not_drive_the_colour(client, proteins):
    """Swap the labels: the assessment follows the sequence, not the name."""
    s = client.get("/api/batch/samples").json()[1]
    df = pd.read_csv(io.StringIO(client.get(s["download_url"]).text))
    hbb, lcc = df.loc[df.protein_id == "Human_HBB", "sequence"].iloc[0], df.loc[df.protein_id == "LCC", "sequence"].iloc[0]
    csv = f"protein_id,sequence\nLCC,{hbb}\nHuman_HBB,{lcc}\n"
    rows = {r["protein_id"]: r["assessment"]["category"] for r in _sample_run(client, s, "swap.csv", csv)["results"]}
    assert rows == {"LCC": "red", "Human_HBB": "green"}


def test_single_and_bulk_agree(client, proteins):
    s = client.get("/api/batch/samples").json()
    seqs = {}
    for x in s:
        df = pd.read_csv(io.StringIO(client.get(x["download_url"]).text))
        seqs.update(dict(zip(df.protein_id, df.sequence)))
    isp = proteins.loc[proteins.protein_name == "ISPETase", "sequence"].iloc[0]
    seqs["fragment"] = isp[30:230]
    fasta = "".join(f">{k}\n{v}\n" for k, v in seqs.items())
    bulk = {r["protein_id"]: r["assessment"] for r in run(client, body("all.fasta", fasta))[1]["results"]}
    for k, v in seqs.items():
        single = client.post("/api/sequence/match", json={"sequence": v}).json()["assessment"]
        assert (single["category"], single["rule"], single["metrics"]) == (bulk[k]["category"], bulk[k]["rule"], bulk[k]["metrics"]), k


def test_uploaded_csv_invalid_rows_and_export(client, proteins):
    csv = ("protein_id,sequence\nok," + proteins.sequence[5] + "\nshort,MKVL\nbad,MKVLAXGGLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL\n"
           "missing,\n")
    jid, v = run(client, body("mine.csv", csv))
    rows = {r["protein_id"]: r for r in v["results"]}
    assert rows["ok"]["status"] == "analysed" and rows["ok"]["assessment"]["known_reference"]
    assert "too short" in rows["short"]["errors"][0]
    assert "Invalid characters" in rows["bad"]["errors"][0]
    assert rows["missing"]["errors"] == ["Missing sequence."]
    assert all("assessment" not in rows[k] for k in ("short", "bad", "missing"))
    df = pd.read_csv(io.StringIO(client.get(f"/api/batch/jobs/{jid}/export?format=csv").content.decode("utf-8-sig")))
    assert list(df.evidence_assessment) == ["green", "invalid", "invalid", "invalid"]
    assert {"evidence_assessment_label", "known_characterised_reference", "assessment_rule"} <= set(df.columns)


def test_examples_include_unrelated_control(client):
    ex = client.get("/api/sequence/examples").json()
    names = [e["protein_name"] for e in ex]
    assert {"ISPETase", "LCC", "TfCut2"} <= set(names)
    ctrl = [e for e in ex if e["kind"] == "control"]
    assert len(ctrl) == 1 and "HBB" in ctrl[0]["protein_name"]


def test_rules_endpoint(client):
    r = client.get("/api/evidence/rules").json()
    assert r["z_chance"] < r["z_strong"] and {x["category"] for x in r["rules"]} == {"green", "yellow", "red", "insufficient"}
