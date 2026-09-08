"""
core/brain/language.py

Lightweight language detection for NyxAI TTS routing.

Uses Unicode character block ranges to determine if text is primarily
in Devanagari (Hindi/Marathi), other Indic scripts, or Latin/English.
No external dependencies — pure Python, instant execution.

This is NOT a full language identifier (use langdetect/fasttext for that).
Its sole purpose is to route TTS to the correct engine:
  - Devanagari text → pyttsx3/eSpeak-NG (supports hi, mr)
  - Latin/other     → Kokoro (English TTS)

Usage:
    from core.brain.language import detect_response_language
    lang = detect_response_language("यह एक Python tutorial है।")
    # lang == "hi"
"""

from __future__ import annotations

# ─── Unicode Block Ranges ──────────────────────────────────────────────────────

# Indic script ranges with their primary language codes
_INDIC_RANGES: list[tuple[int, int, str]] = [
    (0x0900, 0x097F, "hi"),  # Devanagari (Hindi / Marathi)
    (0x0A80, 0x0AFF, "gu"),  # Gujarati
    (0x0A00, 0x0A7F, "pa"),  # Gurmukhi (Punjabi)
    (0x0B80, 0x0BFF, "ta"),  # Tamil
    (0x0C00, 0x0C7F, "te"),  # Telugu
    (0x0C80, 0x0CFF, "kn"),  # Kannada
    (0x0D00, 0x0D7F, "ml"),  # Malayalam
    (0x0980, 0x09FF, "bn"),  # Bengali
]

# Marathi-specific vocabulary markers (common words unique to Marathi).
# If Devanagari is detected AND any of these appear, we call it Marathi.
_MARATHI_MARKERS: frozenset[str] = frozenset([
    "आहे", "आहेत", "नाही", "आपण", "तुम्ही", "करा", "सांगा", "मला",
    "हे", "ते", "येथे", "तिथे", "होते", "होईल", "असेल", "म्हणजे",
    "कसे", "काय", "केव्हा", "कोण", "कुठे", "जा", "या", "बघ",
    "मी", "तू", "आम्ही", "ती", "तो", "करूया", "बघूया", "सांगतो",
    "खूप", "खूपच", "छान", "बरं", "ठीक", "बघा", "द्या", "घ्या",
])


def detect_response_language(text: str) -> str:
    """
    Detect the primary language of text for TTS engine routing.

    Examines the Unicode character distribution of the text to determine
    whether it's primarily Devanagari (Hindi/Marathi) or Latin/other.

    For Devanagari text, attempts to distinguish Hindi from Marathi by
    checking for Marathi-specific vocabulary markers.

    Args:
        text: The text to analyze. Typically the LLM's response.

    Returns:
        Language code string:
          - "hi" for Hindi (Devanagari, no strong Marathi markers)
          - "mr" for Marathi (Devanagari with Marathi vocabulary)
          - "en" for English / Latin script (default)
          - Other codes for detected Indic scripts (gu, pa, ta, te, kn, ml, bn)

    Examples:
        >>> detect_response_language("List comprehension एक तरीका है।")
        'hi'
        >>> detect_response_language("हे खूप simple आहे!")
        'mr'
        >>> detect_response_language("Hello! How are you?")
        'en'
        >>> detect_response_language("Yaar, chal karte hain yeh!")
        'en'
    """
    if not text or not text.strip():
        return "en"

    # Count alphabetic characters by script block
    total_alpha = 0
    script_counts: dict[str, int] = {}

    for char in text:
        if not char.isalpha():
            continue
        total_alpha += 1
        cp = ord(char)
        for start, end, lang_code in _INDIC_RANGES:
            if start <= cp <= end:
                script_counts[lang_code] = script_counts.get(lang_code, 0) + 1
                break

    if total_alpha == 0:
        return "en"

    # Find the dominant script
    if not script_counts:
        return "en"

    dominant_lang, dominant_count = max(script_counts.items(), key=lambda x: x[1])
    dominant_ratio = dominant_count / total_alpha

    # Need at least 20% Indic characters to call it an Indic language.
    # Hinglish with a few Devanagari words stays "en" (routed to Kokoro).
    if dominant_ratio < 0.20:
        return "en"

    # For Devanagari: distinguish Hindi vs Marathi using vocabulary markers
    if dominant_lang == "hi":
        words_in_text = set(text.split())
        if words_in_text & _MARATHI_MARKERS:
            return "mr"
        return "hi"

    return dominant_lang


def is_devanagari(text: str) -> bool:
    """
    Return True if the text contains a significant amount of Devanagari script.

    Args:
        text: Text to check.

    Returns:
        True if the dominant detected language is Hindi or Marathi.
    """
    lang = detect_response_language(text)
    return lang in ("hi", "mr")
