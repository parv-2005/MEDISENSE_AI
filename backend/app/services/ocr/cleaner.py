"""Clean & format extracted text (OCR pipeline step)."""
import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_BLANK = re.compile(r"\n{3,}")
# Letter/digit confusions that only make sense *inside* a number token.
_O_IN_NUMBER = re.compile(r"(?<=\d)[Oo](?=\d|\b)|(?<=\d)[Oo](?=\d)")
_L_IN_NUMBER = re.compile(r"(?<=\d)[lI](?=\d|\b)")


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    text = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    text = _CONTROL_CHARS.sub("", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _O_IN_NUMBER.sub("0", text)
    text = _L_IN_NUMBER.sub("1", text)
    text = _MULTI_SPACE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()
