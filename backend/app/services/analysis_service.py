"""AI Analysis stage: prompt Gemini with the extracted text, parse a structured result."""
import json
import re
from typing import Callable

from pydantic import ValidationError

from app.models.schemas import ReportAnalysis

Generator = Callable[[str], str]


class AnalysisError(Exception):
    pass


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# JSON schema handed to Gemini as `response_schema` so the model is constrained
# to emit exactly this shape (structured output mode).
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "report_type": {"type": "string"},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "parameter": {"type": "string"},
                    "value": {"type": "string"},
                    "reference_range": {"type": "string"},
                    "status": {"type": "string", "enum": ["low", "normal", "high", "abnormal", "unknown"]},
                    "explanation": {"type": "string"},
                },
                "required": ["parameter", "value", "status"],
            },
        },
        "abnormal_flags": {"type": "array", "items": {"type": "string"}},
        "insights": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "urgency": {"type": "string", "enum": ["routine", "soon", "urgent", "unknown"]},
        "disclaimer": {"type": "string"},
    },
    "required": ["report_type", "summary", "findings", "abnormal_flags", "insights", "recommendations", "urgency"],
}

SYSTEM_INSTRUCTION = (
    "You are MediSense AI, a careful clinical-report explainer. You read the raw text of a patient's "
    "medical report (lab results, imaging summaries, discharge notes) and explain it in plain language "
    "for the patient. You never invent values that are not in the text, you flag every out-of-range "
    "value, and you are explicit that you are not a substitute for a clinician."
)


def build_analysis_prompt(report_text: str) -> str:
    return (
        "Analyse the following medical report text extracted by OCR (it may contain minor OCR errors).\n\n"
        "Return ONLY a JSON object with these keys:\n"
        '- report_type: short name of the report (e.g. "Complete Blood Count", "Lipid Profile", "MRI Brain").\n'
        "- summary: 3-5 sentence plain-language overview for the patient.\n"
        "- findings: one entry per measured parameter found in the text with parameter, value (with units),\n"
        '  reference_range (as printed, or "" if absent), status (low|normal|high|abnormal|unknown) and a '
        "one-sentence explanation.\n"
        '- abnormal_flags: list of "<parameter> <low/high/abnormal>" strings for every out-of-range value.\n'
        "- insights: 2-5 bullet-style observations connecting the findings (patterns, what they commonly indicate).\n"
        "- recommendations: 2-5 practical next steps (follow-up tests, questions to ask the doctor, lifestyle notes).\n"
        "- urgency: routine | soon | urgent | unknown - how quickly a clinician should review this.\n"
        "- disclaimer: a sentence stating this is not a substitute for professional medical advice and the "
        "patient should consult a doctor.\n\n"
        "Rules: do not diagnose; do not invent values; if the text is not a medical report, say so in summary "
        "and return empty lists.\n\n"
        "=== REPORT TEXT START ===\n"
        f"{report_text}\n"
        "=== REPORT TEXT END ===\n"
    )


def parse_analysis(raw: str) -> ReportAnalysis:
    cleaned = _FENCE.sub("", (raw or "").strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Sometimes the model wraps JSON in prose - grab the outermost object.
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise AnalysisError("Gemini did not return JSON.")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Gemini returned malformed JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AnalysisError("Gemini returned JSON that is not an object.")
    try:
        return ReportAnalysis.model_validate(data)
    except ValidationError as exc:
        raise AnalysisError(f"Analysis JSON failed validation: {exc}") from exc


def analyze_report(report_text: str, generate: Generator) -> tuple[ReportAnalysis, str]:
    """Run the full analysis step. `generate` is injected so tests never hit the network."""
    if not report_text or not report_text.strip():
        raise AnalysisError("No extracted text to analyse. Run extraction first.")
    raw = generate(build_analysis_prompt(report_text))
    return parse_analysis(raw), raw
