"""Conservative title identity for alternate editions of the same work."""
import re
import unicodedata


EDITION_SUFFIX = re.compile(
    r"\s*(?:[.,\-:|]\s*)?(?:ed(?:icion)?\.?\s+(?:coleccionista|especial|ilustrada|limitada|bolsillo)|nueva\s+presentacion)\b.*$",
    re.IGNORECASE,
)
EDITION_PARENTHESIS = re.compile(
    r"\s*\((?:ed(?:icion)?\.?\s+(?:minalima|coleccionista|especial|ilustrada|limitada|bolsillo|espanola))\)\s*",
    re.IGNORECASE,
)


def canonical_book_title(title):
    """Normalize typography and explicit edition labels, preserving volume/subtitle."""
    value = unicodedata.normalize("NFKD", title or "")
    value = "".join(character for character in value if not unicodedata.combining(character)).casefold().strip()
    value = EDITION_PARENTHESIS.sub(" ", value)
    value = EDITION_SUFFIX.sub("", value)
    return re.sub(r"[\W_]+", " ", value, flags=re.UNICODE).strip()


def canonical_title_variants(title):
    """Extract each title from bilingual provider labels separated with a slash."""
    variants = {canonical_book_title(part) for part in re.split(r"\s+/\s+", title or "")}
    variants.discard("")
    return variants


def bibliographic_title(info):
    """Preserve meaningful subtitles even when a provider sends a separate field."""
    title = info.get("title") or ""
    subtitle = info.get("subtitle") or ""
    normalized = canonical_book_title(subtitle)
    if normalized and normalized not in canonical_book_title(title):
        return title + ": " + subtitle
    return title


def canonical_match_title(title):
    """A comparison-only title that ignores grammatical glue across translations."""
    stopwords = {"a", "and", "de", "del", "el", "en", "la", "las", "los", "of", "the", "y"}
    return " ".join(word for word in canonical_book_title(title).split() if word not in stopwords)


def canonical_author_name(author):
    value = unicodedata.normalize("NFKD", str(author or ""))
    value = "".join(character for character in value if not unicodedata.combining(character)).casefold()
    # Initials arrive as both "J. K." and "JK" depending on the provider.
    if value.strip() in {"", "unknown", "anonymous", "anonimo", "sin autor", "autor desconocido"}:
        return ""
    if "," in value:
        surname, given = value.split(",", 1)
        value = given + " " + surname
    return "".join(re.findall(r"\w+", value, flags=re.UNICODE))


def canonical_work_key(title, authors=None):
    """Identify a work by normalized title and authors to preserve homonyms."""
    names = [canonical_author_name(author) for author in authors or []]
    if not names or not all(names) or not canonical_book_title(title):
        return None
    return canonical_book_title(title) + "::" + "|".join(sorted(set(names)))


def identity_matches(left_title, left_authors, right_title, right_authors):
    """Known, complete author sets and an explicit title variant are required."""
    left = canonical_work_key(left_title, left_authors)
    right = canonical_work_key(right_title, right_authors)
    return bool(left and right and left.split("::", 1)[1] == right.split("::", 1)[1]
                and canonical_title_variants(left_title) & canonical_title_variants(right_title))


def duplicate_candidate(left_title, left_authors, right_title, right_authors):
    """Review suggestion only: never use this result to merge or group records."""
    def candidate_title(title):
        value = canonical_book_title(title)
        value = re.sub(r"\s+saga\s+.+\s+1$", "", value)
        return canonical_match_title(value)
    left_names = {canonical_author_name(name) for name in left_authors or []} - {""}
    right_names = {canonical_author_name(name) for name in right_authors or []} - {""}
    if left_names and right_names and left_names != right_names:
        return False
    return bool(candidate_title(left_title) and candidate_title(left_title) == candidate_title(right_title))
