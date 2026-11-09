"""Bulk input parsing and validation (pet_explorer.batch)."""

import io
import sys
from pathlib import Path

import matplotlib
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet_explorer import batch as B, config as C  # noqa: E402

matplotlib.use("Agg")

SEQ = "MNFPRASRLMQAAVLGGLMAVSAAATAQTNPYARGPNPTAASLEASAGPFTVRSFTVSRPSGYGAGTVYYPTNAGGTVGAIAIVPGYTARQSSIKWWGPRLASHGFVVITIDTNSTLDQPSSRSSQQMAALRQVASLNGTSSSPIYGKVDTARMGVMGWSMGGGGSLISAANNPSLKAAAPQAPWDSSTNFSSVTVPTLIFACENDSIAPVNSSALPIYDSMSRNAKQFLEINGGSHSCANSGNSNQALIGKKGVAWMKRFMDNDTRYSTFACENPNSTRVSDFRTANCS"


def test_fasta_records_keep_ids_and_organisms():
    text = f">sp|A0A0K8P6T7|PETH_IDESA PETase OS=Ideonella sakaiensis OX=1547922\n{SEQ[:120]}\n{SEQ[120:]}\n>b [Thermobifida fusca]\n{SEQ}\n"
    recs = B.parse_upload("x.fasta", text.encode())["records"]
    assert [r.protein_id for r in recs] == ["sp|A0A0K8P6T7|PETH_IDESA", "b"]
    assert recs[0].organism == "Ideonella sakaiensis" and recs[1].organism == "Thermobifida fusca"
    assert recs[0].sequence == SEQ and recs[0].status == "valid"
    assert recs[1].status == "duplicate" and recs[1].duplicate_of == 1


def test_per_row_errors_do_not_fail_the_batch():
    text = f">ok\n{SEQ}\n>dna\n{'ATGC' * 20}\n>bad\n{SEQ[:50]}BZX\n>short\nMKV\n>empty\n"
    recs = {r.protein_id: r for r in B.parse_upload("x.fa", text.encode())["records"]}
    assert recs["ok"].status == "valid"
    assert "DNA" in recs["dna"].errors[0]
    assert "Invalid characters" in recs["bad"].errors[0]
    assert "too short" in recs["short"].errors[0]
    assert recs["empty"].errors == ["Missing sequence."]


def test_csv_mapping_is_guessed_and_original_rows_kept():
    csv = f"Accession,Organism,AA sequence\nP1,Ideonella sakaiensis,{SEQ}\nP2,,\n,X,{SEQ[::-1]}\n"
    p = B.parse_upload("t.csv", csv.encode())
    assert p["mapping"] == {"protein_id": "Accession", "sequence": "AA sequence", "organism": "Organism"}
    recs = p["records"]
    assert [r.source for r in recs] == ["row 2", "row 3", "row 4"]
    assert recs[1].errors == ["Missing sequence."]
    assert recs[2].protein_id == "row_3" and recs[2].warnings


def test_explicit_mapping_overrides_guess():
    csv = f"a,b\n{SEQ},name1\n"
    recs = B.parse_upload("t.csv", csv.encode(), {"protein_id": "b", "sequence": "a", "organism": None})["records"]
    assert recs[0].protein_id == "name1" and recs[0].status == "valid"
    with pytest.raises(B.UploadError):
        B.parse_upload("t.csv", csv.encode(), {"sequence": "missing"})


def test_xlsx_is_read_as_data():
    buf = io.BytesIO()
    pd.DataFrame({"id": ["E1", "E2"], "sequence": [SEQ, "=HYPERLINK(\"x\")"]}).to_excel(buf, index=False)
    recs = B.parse_upload("t.xlsx", buf.getvalue())["records"]
    assert recs[0].status == "valid"
    assert recs[1].status == "invalid"   # formula text is just an invalid sequence, never evaluated


def test_plain_text_blocks_and_id_lines():
    assert len(B.parse_upload("s.txt", f"{SEQ[:100]}\n{SEQ[100:]}\n\n{SEQ[::-1]}\n".encode())["records"]) == 2
    recs = B.parse_upload("s.txt", f"A1\t{SEQ}\nA2 {SEQ[::-1]}\n".encode())["records"]
    assert [r.protein_id for r in recs] == ["A1", "A2"]


def test_pdf_text_layer_candidates(tmp_path):
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.05, 0.9, "Table S1. Enzymes used in this study", fontsize=8)
    fig.text(0.05, 0.85, f"Enz1  {SEQ[:90]}", fontsize=5, family="monospace")
    fig.text(0.05, 0.80, f"Enz2  {SEQ[60:150]}", fontsize=5, family="monospace")
    path = tmp_path / "t.pdf"
    fig.savefig(path)
    plt.close(fig)
    p = B.parse_upload("t.pdf", path.read_bytes())
    assert p["requires_confirmation"]
    recs = p["records"]
    assert [r.protein_id for r in recs] == ["Enz1", "Enz2"]
    assert recs[0].sequence == SEQ[:90] and recs[0].source == "page 1" and recs[0].warnings


@pytest.mark.parametrize("name,msg", [("a.xls", ".xlsx"), ("a.xlsm", ".xlsx"), ("a.exe", "Unsupported")])
def test_rejected_types(name, msg):
    with pytest.raises(B.UploadError, match=msg):
        B.parse_upload(name, b"x")


def test_limits():
    with pytest.raises(B.UploadError, match="larger"):
        B.parse_upload("a.fasta", b">" + b"A" * (B.MAX_FILE_BYTES + 1))
    many = "".join(f">s{i}\n{SEQ}\n" for i in range(B.MAX_RECORDS + 1))
    with pytest.raises(B.UploadError, match="limit"):
        B.parse_upload("a.fasta", many.encode())


def test_profile_matches_feature_table():
    prot = pd.read_csv(C.F_PROTEINS).head(3)
    table = pd.read_csv(C.CLUSTERING / "sequence_features.csv").set_index("protein_id")
    for pid, seq in zip(prot.protein_id, prot.sequence):
        pr = B.profile(seq)
        assert pr["length"] == len(seq)
        assert abs(pr["physicochemical"]["isoelectric_point"] - table.loc[pid, "isoelectric_point"]) < 0.01
        assert abs(sum(pr["composition"].values()) - 100) < 0.1
        assert pr["motifs"]["count"] == table.loc[pid, "gxsxg_count"]
