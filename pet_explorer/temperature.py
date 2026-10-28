"""Feature 3 - experimental temperature analysis.

Builds three tables from pazy_polymer_assays.json.gz + the feasibility
assay outcomes:

  pet_measurements.csv            one row per PET measurement (value, unit, analyte...)
  pet_temperature_assays.csv      one row per PET assay (temperature, pH, material,
                                  method, outcome, DOI, cluster)
  protein_temperature_summary.csv one row per protein

Rules that keep the analysis honest:
  * The highest temperature tested is NOT treated as the optimum.
  * A "best tested temperature" is reported only inside a COMPARABLE SERIES:
    same protein, paper, metric, analyte, unit, pH, duration, enzyme loading
    and experiment context, with >= 3 temperatures. Even then it is the best
    of the tested temperatures, not a true optimum, and it is flagged when it
    sits at the edge of the tested range.
  * Values with different units/methods are never pooled. Cross-protein
    activity comparisons use only the two standardised screens (one protocol each).
"""

import gzip
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C, plots, preprocess

sys.path.insert(0, str(C.ROOT))
from analyze_pet_dataset import classify_measurement  # noqa: E402  (reuse validated rules)

SCREEN_D3 = ("10.1038/s41467-022-35237-x", "Table D3")
SCREEN_ACS = "10.1021/acscatal.5c03460"
SERIES_KEY = ["protein_id", "literature_doi", "metric_type", "analyte", "unit", "ph", "duration_value",
              "duration_unit", "material_name", "enzyme_preparation", "enzyme_concentration",
              "enzyme_amount", "experiment_context"]


def load_records():
    with gzip.open(C.F_ASSAYS, "rt") as fh:
        return json.load(fh)


def build_measurements(records):
    rows = []
    for ri, r in enumerate(records):
        for ai, a in enumerate(r["assays"]):
            if a["substrate"] != "PET":
                continue
            c = a["conditions"]
            add = c.get("additional_conditions") or {}
            for mi, m in enumerate(a["measurements"]):
                call, reason = classify_measurement(m)
                rows.append({
                    "record_index": ri, "assay_index": ai, "measurement_index": mi,
                    "protein_id": r["protein_id"], "literature_doi": r["literature_doi"],
                    "temperature_c": c.get("temperature_c"), "ph": c.get("ph"),
                    "duration_value": c.get("duration_value"), "duration_unit": c.get("duration_unit"),
                    "material_name": a["material"].get("reported_name"),
                    "enzyme_preparation": c.get("enzyme_preparation"),
                    "enzyme_concentration": f"{c.get('enzyme_concentration_value')} {c.get('enzyme_concentration_unit') or ''}".strip(),
                    "enzyme_amount": f"{c.get('enzyme_amount_value')} {c.get('enzyme_amount_unit') or ''}".strip(),
                    "experiment_context": add.get("experiment_context") or "",
                    "metric_type": m.get("metric_type"), "analyte": m.get("analyte"),
                    "value": m.get("value"), "unit": m.get("unit"), "qualifier": m.get("qualifier"),
                    "uncertainty": m.get("uncertainty_value"), "uncertainty_type": m.get("uncertainty_type"),
                    "categorical_result": m.get("categorical_result"),
                    "value_digitised_from_figure": m.get("value_is_digitized"),
                    "measurement_call": call, "measurement_reason": reason,
                    "reported_result": m.get("reported_result"),
                })
    return pd.DataFrame(rows)


def build_assays(assign):
    a = pd.read_csv(C.F_ASSAY_RECORDS)
    a = a.merge(assign[["protein_id", "cluster", "subcluster"]], on="protein_id", how="left")
    a["in_pet_active_set"] = a.cluster.notna()
    a["degradation_detected"] = a.assay_outcome.map({"POS": "detected", "NEG": "not detected",
                                                     "UNCLEAR": "unclear", "EXCLUDED": "excluded"})
    cols = ["protein_id", "protein_name", "cluster", "subcluster", "in_pet_active_set", "temperature_c", "ph",
            "duration_value", "duration_unit", "material_name", "material_form", "crystallinity_percent",
            "enzyme_preparation", "detection_methods", "metric_types", "max_value", "units",
            "degradation_detected", "outcome_reason", "literature_doi", "experiment_context",
            "record_index", "assay_index"]
    return a[cols]


def comparable_series(meas):
    m = meas[(meas.measurement_call.isin(["POS", "NEG"])) & meas.value.notna() & meas.temperature_c.notna()]
    m = m.assign(**{k: m[k].fillna("") for k in SERIES_KEY if m[k].dtype == object})
    m = m.assign(ph=m.ph.fillna(-1), duration_value=m.duration_value.fillna(-1))
    rows = []
    for key, g in m.groupby(SERIES_KEY, dropna=False):
        per_t = g.groupby("temperature_c").value.max().sort_index()
        if len(per_t) < 3:
            continue
        best_t = per_t.idxmax()
        rows.append({
            **dict(zip(SERIES_KEY, key)),
            "n_temperatures": len(per_t),
            "temperatures_c": "; ".join(f"{t:g}" for t in per_t.index),
            "values": "; ".join(f"{v:g}" for v in per_t.values),
            "best_tested_temperature_c": best_t,
            "best_value": per_t.max(),
            "all_zero": bool((per_t == 0).all()),
            "best_at_edge": "highest tested" if best_t == per_t.index.max()
            else "lowest tested" if best_t == per_t.index.min() else "interior",
        })
    s = pd.DataFrame(rows)
    s["ph"] = s.ph.replace(-1, np.nan)
    s["duration_value"] = s.duration_value.replace(-1, np.nan)
    return s


def fmt_temps(values):
    v = sorted({float(x) for x in values if pd.notna(x)})
    return "; ".join(f"{x:g}" for x in v)


def protein_summary(assays, series, proteins):
    out = []
    for pid, g in assays[assays.in_pet_active_set].groupby("protein_id"):
        temps = g.temperature_c.dropna()
        pos_t = set(g.loc[g.degradation_detected == "detected", "temperature_c"].dropna())
        neg_t = set(g.loc[g.degradation_detected == "not detected", "temperature_c"].dropna()) - pos_t
        n_t = temps.nunique()
        s = series[(series.protein_id == pid) & ~series.all_zero]
        if n_t == 0:
            status = "No temperature recorded"
        elif n_t == 1:
            status = "Tested at one temperature only - insufficient to determine a temperature optimum"
        elif n_t == 2:
            status = "Tested at two temperatures - activity can be compared, but an optimum cannot be determined"
        elif s.empty:
            status = ("Several temperatures tested, but not within one comparable assay series - "
                      "optimum not determinable")
        else:
            bests = s.best_tested_temperature_c
            status = (f"{len(s)} comparable series with >= 3 temperatures; best TESTED temperature "
                      f"{fmt_temps(bests).replace('; ', ', ')} °C (not a true optimum")
            status += "; at least one at the edge of the tested range)" if (s.best_at_edge != "interior").any() else ")"
        category = ("no temperature" if n_t == 0 else "one temperature" if n_t == 1 else
                    "two temperatures" if n_t == 2 else "no comparable series" if s.empty else
                    "comparable series (>=3 temperatures)")
        out.append({
            "protein_id": pid,
            "protein_name": g.protein_name.iloc[0],
            "cluster": g.cluster.iloc[0], "subcluster": g.subcluster.iloc[0],
            "optimum_status_category": category,
            "n_pet_assays": len(g),
            "n_temperatures_tested": int(n_t),
            "temperatures_tested_c": fmt_temps(temps),
            "temperatures_with_activity_c": fmt_temps(pos_t),
            "temperatures_without_detected_activity_c": fmt_temps(neg_t),
            "min_active_temperature_c": min(pos_t) if pos_t else np.nan,
            "max_active_temperature_c": max(pos_t) if pos_t else np.nan,
            "n_comparable_series": len(s),
            "temperature_optimum_status": status,
            "ph_values_tested": fmt_temps(g.ph),
            "detection_methods": "; ".join(sorted({x for v in g.detection_methods.dropna() for x in v.split("; ")}))[:300],
            "references": "; ".join(sorted(g.literature_doi.unique())),
        })
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- figures
def fig_tested_temperatures(assays):
    a = assays[assays.in_pet_active_set & assays.temperature_c.notna()]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(a.temperature_c, bins=np.arange(2.5, 95, 5), color=plots.SERIES[0], edgecolor="white", linewidth=1.5)
    ax.set_xlabel("Assay temperature (°C), 5 °C bins", color=plots.INK2, fontsize=9)
    ax.set_ylabel("PET assay records", color=plots.INK2, fontsize=9)
    plots.title(ax, f"Temperatures at which PET assays were run (n = {len(a):,} assays)")
    plots.style(ax)
    plots.save(fig, "t01_tested_temperatures.png")


def fig_activity_by_temperature(assays):
    a = assays[assays.in_pet_active_set & assays.temperature_c.notna()
               & assays.degradation_detected.isin(["detected", "not detected"])]
    bins = [0, 30, 40, 50, 60, 70, 80, 100]
    labels = ["<30", "30-39", "40-49", "50-59", "60-69", "70-79", "≥80"]
    a = a.assign(tbin=pd.cut(a.temperature_c, bins, right=False, labels=labels))
    t = a.groupby(["tbin", "degradation_detected"], observed=False).size().unstack(fill_value=0)
    t = t.reindex(columns=["detected", "not detected"], fill_value=0)
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    x = np.arange(len(t))
    ax.bar(x, t["detected"], color=plots.POS_COLOR, edgecolor="white", linewidth=1.5, label="degradation detected")
    ax.bar(x, t["not detected"], bottom=t["detected"], color=plots.NEG_COLOR, edgecolor="white", linewidth=1.5,
           label="nothing detected")
    tot = t.sum(axis=1)
    for xi, d, n in zip(x, t["detected"], tot):
        if n:
            ax.text(xi, n, f"{100 * d / n:.0f}%\nn={n}", ha="center", va="bottom", fontsize=7.5, color=plots.INK2)
    ax.set_xticks(x, t.index)
    ax.set_xlabel("Assay temperature (°C)", color=plots.INK2, fontsize=9)
    ax.set_ylabel("PET assays", color=plots.INK2, fontsize=9)
    ax.set_ylim(0, tot.max() * 1.2)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    plots.title(ax, "PET degradation observations by temperature (labels = % detected)")
    plots.style(ax)
    plots.save(fig, "t02_activity_by_temperature.png")


def fig_temperature_by_cluster(assays):
    a = assays[assays.in_pet_active_set & (assays.degradation_detected == "detected") & assays.temperature_c.notna()]
    groups = sorted(a.subcluster.unique(), key=plots.group_key)
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    rng = np.random.default_rng(0)
    for i, gname in enumerate(groups):
        # one point per protein x temperature (assays at the same temperature are not independent)
        v = a[a.subcluster == gname].drop_duplicates(["protein_id", "temperature_c"]).temperature_c
        ax.scatter(i + rng.uniform(-0.25, 0.25, len(v)), v, s=12, color=plots.SERIES[0], alpha=0.45, edgecolor="none")
        ax.hlines(v.median(), i - 0.3, i + 0.3, color=plots.INK, lw=2)
        ax.text(i, 92, f"n={a[a.subcluster == gname].protein_id.nunique()}", ha="center", fontsize=7.5, color=plots.INK2)
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylim(15, 97)
    ax.set_ylabel("Temperature with detected PET activity (°C)", color=plots.INK2, fontsize=9)
    plots.title(ax, "Temperatures with detected activity, by cluster (bar = median)")
    plots.style(ax)
    plots.save(fig, "t03_active_temperature_by_cluster.png")


def screen_d3_table(meas):
    s = meas[(meas.literature_doi == SCREEN_D3[0]) & meas.experiment_context.str.contains(SCREEN_D3[1])]
    return s.groupby(["protein_id", "temperature_c"]).value.max().unstack()


def fig_screen_d3(meas, names):
    t = screen_d3_table(meas)
    if t.empty:
        return t
    t = t.loc[t.max(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(6.5, 7))
    im = ax.imshow(np.log10(t.values + 1), cmap="Blues", aspect="auto")
    ax.set_xticks(range(t.shape[1]), [f"{c:g}" for c in t.columns])
    ax.set_yticks(range(t.shape[0]), [names.get(i, i) for i in t.index], fontsize=7.5)
    for (i, j), v in np.ndenumerate(t.values):
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=6.5,
                color="white" if np.log10(v + 1) > 0.6 * np.log10(t.values.max() + 1) else plots.INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.04)
    cb.set_label("log10(mg/L + 1)", fontsize=8)
    ax.set_xlabel("Temperature (°C)", color=plots.INK2, fontsize=9)
    ax.set_title("Standardised screen (one protocol): max aromatic products over\ntested pH, 96 h, amorphous PET film (mg/L; 500 = '>500', assay ceiling)",
                 loc="left", fontsize=10, fontweight="bold")
    plots.save(fig, "t04_standardised_screen_d3.png")
    return t


def fig_screen_acs(meas, names):
    s = meas[(meas.literature_doi == SCREEN_ACS) & (meas.metric_type == "conversion_percent")]
    t = s.groupby(["protein_id", "temperature_c"]).value.max().unstack()
    if t.empty or t.shape[1] < 2:
        return t
    fig, ax = plt.subplots(figsize=(6.5, 4))
    lo, hi = t.columns.min(), t.columns.max()
    ax.scatter(t[lo], t[hi], s=22, color=plots.SERIES[0], edgecolor="white", linewidth=0.8)
    m = np.nanmax(t.values) * 1.05
    ax.plot([0, m], [0, m], color=plots.GREY, lw=1, ls="--")
    ax.text(m * 0.98, m * 0.92, "equal", color=plots.INK2, fontsize=8, ha="right")
    ax.set_xlabel(f"Best conversion at {lo:g} °C (%; max over pH)", color=plots.INK2, fontsize=9)
    ax.set_ylabel(f"Best conversion at {hi:g} °C (%)", color=plots.INK2, fontsize=9)
    above = int((t[hi] > t[lo]).sum())
    plots.title(ax, f"Standardised screen ({len(t)} proteins): {above} convert more PET at {hi:g} °C")
    plots.style(ax, grid="both")
    plots.save(fig, "t05_standardised_screen_40_vs_60.png")
    return t


def run():
    C.ensure_dirs()
    proteins = preprocess.load_proteins()
    assign = pd.read_csv(C.CLUSTERING / "cluster_assignments.csv")
    records = load_records()
    meas = build_measurements(records)
    meas = meas.merge(assign[["protein_id", "subcluster"]], on="protein_id", how="left")
    meas.to_csv(C.TEMPERATURE / "pet_measurements.csv", index=False)
    assays = build_assays(assign)
    assays.to_csv(C.TEMPERATURE / "pet_temperature_assays.csv", index=False)
    series = comparable_series(meas)
    series.to_csv(C.TEMPERATURE / "comparable_temperature_series.csv", index=False)
    summary = protein_summary(assays, series, proteins)
    summary.to_csv(C.TEMPERATURE / "protein_temperature_summary.csv", index=False)

    names = dict(zip(proteins.protein_id, proteins.protein_name))
    fig_tested_temperatures(assays)
    fig_activity_by_temperature(assays)
    fig_temperature_by_cluster(assays)
    d3 = fig_screen_d3(meas, names)
    acs = fig_screen_acs(meas, names)
    d3.to_csv(C.TEMPERATURE / "screen_d3_max_product_by_temperature.csv")
    acs.to_csv(C.TEMPERATURE / "screen_acs_max_conversion_by_temperature.csv")

    by_cluster = (assays[assays.in_pet_active_set & (assays.degradation_detected == "detected")]
                  .drop_duplicates(["protein_id", "temperature_c"])
                  .groupby("subcluster").temperature_c.describe()[["count", "min", "25%", "50%", "75%", "max"]])
    by_cluster.to_csv(C.TEMPERATURE / "active_temperature_by_cluster.csv")

    print(f"[stage 3] {len(meas):,} measurements, {len(assays):,} assays, {len(series)} comparable series")
    print(summary.optimum_status_category.value_counts().to_string())
    print(by_cluster.round(1).to_string())
    return summary
