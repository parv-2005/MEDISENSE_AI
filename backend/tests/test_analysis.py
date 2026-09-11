import json

import pytest

from app.services import analysis_service as svc
from app.models.schemas import ReportAnalysis

SAMPLE_TEXT = "Complete Blood Count\nHemoglobin 10.2 g/dL (12.0-16.0)\nWBC 7.1 x10^3/uL (4.0-11.0)"

GOOD_JSON = {
    "report_type": "Complete Blood Count",
    "summary": "Mild anaemia; other values normal.",
    "findings": [
        {"parameter": "Hemoglobin", "value": "10.2 g/dL", "reference_range": "12.0-16.0", "status": "low",
         "explanation": "Below the reference range, suggesting anaemia."},
        {"parameter": "WBC", "value": "7.1 x10^3/uL", "reference_range": "4.0-11.0", "status": "normal",
         "explanation": "Within range."},
    ],
    "abnormal_flags": ["Hemoglobin low"],
    "insights": ["Low haemoglobin can cause fatigue."],
    "recommendations": ["Discuss iron studies with your doctor."],
    "urgency": "routine",
    "disclaimer": "Not medical advice.",
}


def test_prompt_contains_report_text_and_safety_instructions():
    prompt = svc.build_analysis_prompt(SAMPLE_TEXT)
    assert SAMPLE_TEXT in prompt
    assert "not a substitute" in prompt.lower() or "consult" in prompt.lower()
    assert "JSON" in prompt


def test_parse_accepts_plain_json():
    parsed = svc.parse_analysis(json.dumps(GOOD_JSON))
    assert isinstance(parsed, ReportAnalysis)
    assert parsed.findings[0].status == "low"
    assert parsed.abnormal_flags == ["Hemoglobin low"]


def test_parse_strips_markdown_code_fences():
    fenced = "```json\n" + json.dumps(GOOD_JSON) + "\n```"
    assert svc.parse_analysis(fenced).summary == GOOD_JSON["summary"]


def test_parse_fills_defaults_for_missing_optional_fields():
    minimal = {"summary": "ok", "findings": []}
    parsed = svc.parse_analysis(json.dumps(minimal))
    assert parsed.recommendations == []
    assert parsed.urgency == "unknown"
    assert parsed.disclaimer  # always present, even if the model forgot it


def test_parse_normalises_status_casing_and_unknown_values():
    data = dict(GOOD_JSON)
    data["findings"] = [{"parameter": "X", "value": "1", "status": "HIGH"},
                        {"parameter": "Y", "value": "2", "status": "weird"}]
    parsed = svc.parse_analysis(json.dumps(data))
    assert parsed.findings[0].status == "high"
    assert parsed.findings[1].status == "unknown"


def test_parse_raises_on_garbage():
    with pytest.raises(svc.AnalysisError):
        svc.parse_analysis("Sorry, I cannot help with that.")


def test_analyze_report_uses_injected_generator_and_returns_model_and_raw():
    calls = []

    def fake_generate(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps(GOOD_JSON)

    analysis, raw = svc.analyze_report(SAMPLE_TEXT, generate=fake_generate)
    assert len(calls) == 1 and SAMPLE_TEXT in calls[0]
    assert analysis.report_type == "Complete Blood Count"
    assert raw == json.dumps(GOOD_JSON)


def test_analyze_report_rejects_empty_text():
    with pytest.raises(svc.AnalysisError):
        svc.analyze_report("   ", generate=lambda p: "{}")
