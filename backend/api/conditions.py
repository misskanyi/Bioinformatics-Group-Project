"""Activity Conditions: reported PET assay conditions and outcomes."""

from fastapi import APIRouter

from ..services import store

router = APIRouter()

ASSAY_FIELDS = ["protein_id", "protein_name", "subcluster", "temperature_c", "ph", "duration_value",
                "duration_unit", "material_name", "material_form", "crystallinity_percent", "enzyme_preparation",
                "detection_methods", "metric_types", "degradation_detected", "outcome_reason", "literature_doi"]


@router.get("/conditions")
def conditions():
    a = store.temperature_assays()[ASSAY_FIELDS].copy()
    a["detection_methods"] = a.detection_methods.fillna("").str.slice(0, 160)
    a["material_name"] = a.material_name.fillna("").str.slice(0, 120)
    t = store.temperature_summary()
    s = store.comparable_series()
    s = s[~s.all_zero]
    series = [{"protein_id": int(r.protein_id), "doi": r.literature_doi, "metric": r.metric_type,
               "unit": r.unit, "ph": None if r.ph != r.ph else float(r.ph),
               "temperatures": store.floats(r.temperatures_c), "values": store.floats(r.values),
               "best_tested_temperature_c": float(r.best_tested_temperature_c), "best_at_edge": r.best_at_edge,
               "context": r.experiment_context if isinstance(r.experiment_context, str) else ""}
              for r in s.itertuples()]
    return {
        "assays": [list(r.values()) for r in store.records(a)],
        "assay_fields": ASSAY_FIELDS,
        "proteins": store.records(t[["protein_id", "protein_name", "subcluster", "optimum_status_category",
                                     "n_pet_assays", "n_temperatures_tested", "temperatures_tested_c",
                                     "temperatures_with_activity_c", "temperatures_without_detected_activity_c",
                                     "temperature_optimum_status", "ph_values_tested", "n_comparable_series"]]),
        "series": series,
        "notes": [
            "Each row is one reported assay. Several assays of the same protein are repeated measurements, "
            "not independent proteins.",
            "'Detected' means any direct product/mass-loss metric > 0 or a categorical positive result in that assay.",
            "'Not detected' means the reported method measured zero under those conditions; it does not prove "
            "the enzyme is inactive.",
            "No temperature optimum is claimed. A 'best tested temperature' is shown only inside one comparable "
            "series (same protein, paper, metric, unit, pH, duration and enzyme loading) with >= 3 temperatures.",
        ],
    }
