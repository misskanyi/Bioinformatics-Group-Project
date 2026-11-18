"""Validate an executed notebook against the project brief.

    python scripts/check_notebook.py notebooks/pet_enzyme_explorer.ipynb [--report report.md]

Fails (exit 1) unless:
  * every code cell was executed and none produced an error;
  * the eight required stages appear as level-2 headings, in order;
  * the approved research question appears verbatim;
  * Stage 4 contains at least three plots drawn by notebook code (PNG outputs of cells that
    call matplotlib), not only pre-rendered image files;
  * stages 2-7 have at least one code cell with saved output, and every stage has explanation text.
"""

import argparse
import json
import re
import sys
from pathlib import Path

RESEARCH_QUESTION = ("How can protein sequence analysis and machine learning help identify promising "
                     "PET-degrading enzyme candidates for further laboratory testing?")
STAGES = [
    ("1", r"research question.*objectives.*hypothes"),
    ("2", r"data acquisition"),
    ("3", r"pre-?processing.*quality control"),
    ("4", r"exploratory data analysis"),
    ("5", r"core analysis"),
    ("6", r"biological interpretation"),
    ("7", r"machine learning"),
    ("8", r"conclusions.*limitations"),
]
MIN_EDA_PLOTS = 3


def text(cell):
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else s


def check(path):
    nb = json.loads(Path(path).read_text())
    cells = nb["cells"]
    problems, facts = [], {}

    code = [c for c in cells if c["cell_type"] == "code"]
    unexecuted = [i for i, c in enumerate(code) if c.get("execution_count") is None]
    errors = [(i, o.get("ename"), o.get("evalue")) for i, c in enumerate(code)
              for o in c.get("outputs", []) if o.get("output_type") == "error"]
    facts["code cells"] = len(code)
    facts["executed"] = len(code) - len(unexecuted)
    facts["errors"] = len(errors)
    if unexecuted:
        problems.append(f"{len(unexecuted)} code cell(s) not executed (first: code cell {unexecuted[0]})")
    for i, name, value in errors:
        problems.append(f"code cell {i} raised {name}: {value}")

    md_all = " ".join(text(c) for c in cells if c["cell_type"] == "markdown")
    rq_found = RESEARCH_QUESTION in re.sub(r"\s+", " ", md_all.replace(">", " "))
    facts["research question verbatim"] = rq_found
    if not rq_found:
        problems.append("approved research question not found verbatim")

    # stage boundaries from level-2 headings
    heads = [(i, text(c).splitlines()[0]) for i, c in enumerate(cells)
             if c["cell_type"] == "markdown" and text(c).startswith("## ")]
    pos = []
    for num, pattern in STAGES:
        hit = [i for i, h in heads if re.match(rf"##\s*{num}\.", h) and re.search(pattern, h, re.I)]
        if not hit:
            problems.append(f"stage {num} heading missing (expected '## {num}. ...' matching /{pattern}/)")
            pos.append(None)
        else:
            pos.append(hit[0])
    found = [p for p in pos if p is not None]
    if found != sorted(found):
        problems.append("stages are not in the required order")
    facts["stages found"] = sum(p is not None for p in pos)

    bounds = pos + [len(cells)]
    per_stage = {}
    for k, (num, _) in enumerate(STAGES):
        if pos[k] is None:
            continue
        nxt = next((b for b in bounds[k + 1:] if b is not None), len(cells))
        block = cells[pos[k]:nxt]
        has_output = any(c["cell_type"] == "code" and c.get("outputs") for c in block)
        has_text = sum(len(text(c)) for c in block if c["cell_type"] == "markdown") > 300
        plots = sum(1 for c in block if c["cell_type"] == "code"
                    and re.search(r"plt\.|subplots|\.hist\(|\.bar", text(c))
                    for o in c.get("outputs", []) if "image/png" in o.get("data", {}))
        per_stage[num] = {"code_output": has_output, "interpretation": has_text, "code_plots": plots}
        if num not in ("1", "8") and not has_output:   # question and conclusions are prose
            problems.append(f"stage {num} has no code cell with saved output")
        if not has_text:
            problems.append(f"stage {num} has no substantial explanation text")
    eda = per_stage.get("4", {}).get("code_plots", 0)
    facts["EDA plots drawn by notebook code"] = eda
    if eda < MIN_EDA_PLOTS:
        problems.append(f"stage 4 has {eda} plot(s) drawn by notebook code; at least {MIN_EDA_PLOTS} required")
    facts["PNG outputs (all)"] = sum("image/png" in o.get("data", {}) for c in code for o in c.get("outputs", []))
    return problems, facts, per_stage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notebook")
    ap.add_argument("--report", help="write a Markdown report here")
    args = ap.parse_args()
    problems, facts, per_stage = check(args.notebook)
    lines = [f"# Notebook check: {args.notebook}", "", "| Check | Value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in facts.items()]
    lines += ["", "| Stage | Code output | Interpretation | Plots drawn in code |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['code_output']} | {v['interpretation']} | {v['code_plots']} |" for k, v in per_stage.items()]
    lines += ["", "## Result", ""] + ([f"- FAIL: {p}" for p in problems] or ["- PASS"])
    report = "\n".join(lines) + "\n"
    print(report)
    if args.report:
        Path(args.report).write_text(report)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
