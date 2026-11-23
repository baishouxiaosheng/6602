import re
import unicodedata


_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
)


def normalize_evidence_text(value: str) -> str:
    """Normalize harmless typography differences before trace matching."""
    normalized = unicodedata.normalize("NFKC", value).translate(_QUOTE_TRANSLATION)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def quote_is_present(quote: str, passages: list[str]) -> bool:
    normalized = normalize_evidence_text(quote)
    return bool(normalized) and any(
        normalized in normalize_evidence_text(item) for item in passages
    )
