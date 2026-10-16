"""Conservative title identity for alternate editions of the same work."""
import re
import unicodedata


EDITION_SUFFIX = re.compile(
    r"\s*(?:[.,\-:|]\s*)?(?:(?:ed(?:icion)?\.?\s+)?(?:coleccionista|especial|ilustrada|limitada|bolsillo)|nueva\s+presentacion)\b.*$",
    re.IGNORECASE,
)
FIRST_VOLUME_SUFFIX = re.compile(
    r"\s*(?:[-:|]\s*)?(?:vol(?:umen)?\.?|libro|tomo)\s*(?:1|i)\b.*$",
    re.IGNORECASE,
)
EDITION_PARENTHESIS = re.compile(
    r"\s*\([^)]*(?:ed(?:icion)?\.?|minalima|coleccionista|especial|ilustrada|limitada|bolsillo)[^)]*\)\s*",
    re.IGNORECASE,
)


def canonical_book_title(title):
    """Collapse explicit first-volume and edition labels, without merging sequels."""
    value = unicodedata.normalize("NFKD", title or "")
    value = "".join(character for character in value if not unicodedata.combining(character)).casefold().strip()
    value = EDITION_PARENTHESIS.sub(" ", value)
    value = EDITION_SUFFIX.sub("", value)
    value = FIRST_VOLUME_SUFFIX.sub("", value)
    return re.sub(r"[\W_]+", " ", value, flags=re.UNICODE).strip()


def canonical_title_variants(title):
    """Extract each title from bilingual provider labels separated with a slash."""
    variants = {canonical_book_title(part) for part in re.split(r"\s+/\s+", title or "")}
    variants.discard("")
    return variants


def canonical_match_title(title):
    """A comparison-only title that ignores grammatical glue across translations."""
    stopwords = {"a", "and", "de", "del", "el", "en", "la", "las", "los", "of", "the", "y"}
    return " ".join(word for word in canonical_book_title(title).split() if word not in stopwords)


def canonical_author_name(author):
    value = unicodedata.normalize("NFKD", str(author or ""))
    value = "".join(character for character in value if not unicodedata.combining(character)).casefold()
    # Initials arrive as both "J. K." and "JK" depending on the provider.
    return "".join(re.findall(r"\w+", value, flags=re.UNICODE))


def canonical_work_key(title, authors=None):
    """Identify a work by normalized title and authors to preserve homonyms."""
    normalized_authors = []
    for author in authors or []:
        normalized = unicodedata.normalize("NFKD", str(author))
        normalized = "".join(character for character in normalized if not unicodedata.combining(character)).casefold()
        words = re.findall(r"\w+", normalized, flags=re.UNICODE)
        if words:
            normalized_authors.append(" ".join(sorted(words)))
    return canonical_book_title(title) + "::" + "|".join(sorted(normalized_authors))
