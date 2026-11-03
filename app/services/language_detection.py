"""Language, script and code-mixing detection for citizen messages."""

import re
import unicodedata
from dataclasses import dataclass

LANGUAGE_ENGLISH = "en"
LANGUAGE_HINDI = "hi"
LANGUAGE_TELUGU = "te"
LANGUAGE_HINGLISH = "hinglish"
LANGUAGE_TENGLISH = "tenglish"
LANGUAGE_MIXED = "mixed"
LANGUAGE_UNKNOWN = "unknown"

_TOKEN_PATTERN = re.compile(r"[a-zA-Z]+(?:'[a-zA-Z]+)?")
_DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")
_TELUGU_PATTERN = re.compile(r"[\u0C00-\u0C7F]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")

_ENGLISH_MARKERS = frozenset(
    {
        "a",
        "are",
        "broken",
        "complaint",
        "electricity",
        "garbage",
        "has",
        "have",
        "is",
        "issue",
        "leak",
        "near",
        "need",
        "no",
        "not",
        "please",
        "pothole",
        "power",
        "problem",
        "road",
        "street",
        "supply",
        "the",
        "there",
        "water",
    }
)

_HINGLISH_MARKERS = frozenset(
    {
        "bahut",
        "bijli",
        "chahiye",
        "gali",
        "hai",
        "hain",
        "karna",
        "karo",
        "kripya",
        "mere",
        "mujhe",
        "nahin",
        "nahi",
        "pani",
        "sadak",
        "seva",
        "shikayat",
        "yahan",
    }
)

_TENGLISH_MARKERS = frozenset(
    {
        "avtundi",
        "avuthundi",
        "cheyyandi",
        "chesaru",
        "current",
        "daggara",
        "ekkada",
        "ivvandi",
        "kavali",
        "ledu",
        "neellu",
        "nundi",
        "undi",
        "vachindi",
        "vachindhi",
    }
)


@dataclass(frozen=True, slots=True)
class LanguageDetectionResult:
    """Language detection result consumed by later NLP and bot tasks."""

    language: str
    script: str
    is_code_mixed: bool
    confidence: float
    normalized_text: str
    evidence: tuple[str, ...] = ()

    @property
    def needs_confirmation(self) -> bool:
        """Return whether the interface should ask the citizen to confirm language."""

        return self.language == LANGUAGE_UNKNOWN or self.confidence < 0.55


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while preserving the message meaning."""

    normalized = unicodedata.normalize("NFC", text or "")
    return " ".join(normalized.split())


def _tokens(text: str) -> set[str]:
    """Return lowercase Roman-script tokens from a message."""

    return {token.lower() for token in _TOKEN_PATTERN.findall(text)}


def _script_profile(text: str) -> tuple[int, int, int]:
    """Count Devanagari, Telugu and Latin characters."""

    return (
        len(_DEVANAGARI_PATTERN.findall(text)),
        len(_TELUGU_PATTERN.findall(text)),
        len(_LATIN_PATTERN.findall(text)),
    )


def _script_name(devanagari: int, telugu: int, latin: int) -> str:
    """Return a readable script label from character counts."""

    scripts: list[str] = []
    if devanagari:
        scripts.append("devanagari")
    if telugu:
        scripts.append("telugu")
    if latin:
        scripts.append("latin")
    return "+".join(scripts) if scripts else "none"


def detect_language(text: str) -> LanguageDetectionResult:
    """Detect language and code mixing using scripts and regional word markers."""

    normalized = normalize_text(text)
    devanagari, telugu, latin = _script_profile(normalized)
    script = _script_name(devanagari, telugu, latin)
    if not normalized or not (devanagari or telugu or latin):
        return LanguageDetectionResult(
            language=LANGUAGE_UNKNOWN,
            script="none",
            is_code_mixed=False,
            confidence=0.0,
            normalized_text=normalized,
        )

    if devanagari and telugu:
        return LanguageDetectionResult(
            language=LANGUAGE_MIXED,
            script=script,
            is_code_mixed=True,
            confidence=0.95,
            normalized_text=normalized,
            evidence=("multiple_indic_scripts",),
        )

    if devanagari:
        return LanguageDetectionResult(
            language=LANGUAGE_HINDI,
            script=script,
            is_code_mixed=latin > 0,
            confidence=0.92 if latin else 0.99,
            normalized_text=normalized,
            evidence=("devanagari_script",),
        )

    if telugu:
        return LanguageDetectionResult(
            language=LANGUAGE_TELUGU,
            script=script,
            is_code_mixed=latin > 0,
            confidence=0.92 if latin else 0.99,
            normalized_text=normalized,
            evidence=("telugu_script",),
        )

    tokens = _tokens(normalized)
    hinglish_hits = sorted(tokens & _HINGLISH_MARKERS)
    tenglish_hits = sorted(tokens & _TENGLISH_MARKERS)
    english_hits = sorted(tokens & _ENGLISH_MARKERS)

    if hinglish_hits or tenglish_hits:
        if hinglish_hits and tenglish_hits:
            language = LANGUAGE_MIXED
            evidence = tuple([f"hinglish:{token}" for token in hinglish_hits] + [f"tenglish:{token}" for token in tenglish_hits])
        elif hinglish_hits:
            language = LANGUAGE_HINGLISH
            evidence = tuple(f"hinglish:{token}" for token in hinglish_hits)
        else:
            language = LANGUAGE_TENGLISH
            evidence = tuple(f"tenglish:{token}" for token in tenglish_hits)
        return LanguageDetectionResult(
            language=language,
            script=script,
            is_code_mixed=True,
            confidence=0.84 if english_hits else 0.78,
            normalized_text=normalized,
            evidence=evidence,
        )

    if english_hits:
        return LanguageDetectionResult(
            language=LANGUAGE_ENGLISH,
            script=script,
            is_code_mixed=False,
            confidence=0.82,
            normalized_text=normalized,
            evidence=tuple(f"english:{token}" for token in english_hits),
        )

    return LanguageDetectionResult(
        language=LANGUAGE_UNKNOWN,
        script=script,
        is_code_mixed=False,
        confidence=0.25,
        normalized_text=normalized,
        evidence=("roman_text_without_known_markers",),
    )
