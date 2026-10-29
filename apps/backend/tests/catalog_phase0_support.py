"""Synthetic comparison oracle only; never imported by application code.

The legacy grouping calls the real service against a read-only session double.
Metrics model the audited SQL semantics; they are not database integration tests.
Confirmed links below are fictional editorial decisions, not inferred evidence.
"""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

# Register both sides of User.auth_account without importing the HTTP app.
from app.modules.auth.models import AuthAccount  # noqa: F401
from app.modules.users.models import User  # noqa: F401
from app.modules.books.service import equivalent_work_ids


def scenarios():
    def work(key, title, authors=None):
        return {"id": key, "title": title, "authors": ["Test Author"] if authors is None else authors}

    def review(key, user, work_id, rating, time, status="published"):
        return dict(id=key, user=user, work=work_id, rating=rating, time=time, status=status)

    def reading(key, user, work_id, status, time, archived=False):
        return dict(id=key, user=user, work=work_id, status=status, time=time, archived=archived)

    base = dict(anchor="A", confirmed=[], reviews=[], readings=[])
    return [
        dict(base, name="title_author_only", works=[work("A", "Novel"), work("B", "Novel")],
             reviews=[review("r1", "u1", "A", 5, 1), review("r2", "u2", "B", 1, 2)],
             readings=[reading("l1", "u1", "A", "finished", 1), reading("l2", "u2", "B", "reading", 2)]),
        dict(base, name="confirmed_translation", works=[work("A", "La novela"), work("B", "The novel")],
             confirmed=[["B", "A"]], reviews=[review("r1", "u1", "B", 4, 1)],
             readings=[reading("l1", "u1", "A", "finished", 1)]),
        dict(base, name="transitive_title_bridge", works=[work("A", "Uno"), work("B", "Uno / Two"), work("C", "Two")],
             reviews=[review("r1", "u1", "C", 2, 1)]),
        dict(base, name="latest_private_review", works=[work("A", "Novel"), work("B", "Novel")],
             confirmed=[["B", "A"]],
             reviews=[review("r1", "u1", "A", 5, 1), review("r2", "u1", "B", 2, 2, "hidden")]),
        dict(base, name="overlapping_reader", works=[work("A", "Novel"), work("B", "Novel")],
             confirmed=[["B", "A"]],
             reviews=[review("r1", "u1", "A", 2, 1), review("r2", "u1", "B", 4, 2)],
             readings=[reading("l1", "u1", "A", "finished", 1), reading("l2", "u1", "B", "reading", 2),
                       reading("l3", "u2", "A", "finished", 3, archived=True)]),
        dict(base, name="unknown_author", works=[work("A", "Novel", []), work("B", "Novel")]),
    ]


class SnapshotSession:
    """Only the two SELECT shapes used by equivalent_work_ids are accepted."""
    def __init__(self, works):
        self.works = {w["id"]: w for w in works}

    def get(self, model, key):
        return self.works.get(key)

    def execute(self, statement):
        sql = str(statement)
        if "app.obras_autores" in sql:
            rows = [(w["id"], author) for w in self.works.values() for author in w["authors"]]
        elif "app.ediciones LEFT OUTER JOIN app.fuentes_catalogo" in sql:
            rows = [(SimpleNamespace(work_id=w["id"], title=w["title"]),
                     SimpleNamespace(provider="google-books", payload={"volumeInfo": {
                         "title": w["title"], "authors": w["authors"]}})) for w in self.works.values()]
        else:
            raise AssertionError("Unexpected query in read-only session double")
        return Mock(all=Mock(return_value=rows))


def confirmed_root(key, links):
    parents = dict(links)
    if len(parents) != len(links):
        raise ValueError("Multiple destinations for the same historical work")
    visited = set()
    while key in parents:
        if key in visited:
            raise ValueError("Canonical cycle")
        visited.add(key)
        key = parents[key]
    return key


def latest_per_user(rows):
    latest = {}
    for row in sorted(rows, key=lambda r: (r["time"], r["id"])):
        latest[row["user"]] = row
    return list(latest.values())


def metrics(case, group, canonical=False):
    reviews = [r for r in case["reviews"] if r["work"] in group]
    current = latest_per_user(reviews)  # Rank BEFORE visibility, as public_rating does.
    rated = [Decimal(str(r["rating"])) for r in current
             if r["status"] == "published" and r["rating"] is not None
             and Decimal("0.25") <= Decimal(str(r["rating"])) <= Decimal("5")]
    listed = current if canonical else reviews
    readings = [r for r in case["readings"] if r["work"] in group and not r["archived"]]
    stats = {status: sum(r["status"] == status for r in latest_per_user(readings))
             for status in ("finished", "reading", "abandoned")}
    associations = []
    for reading in readings:
        matches = [r for r in reviews if r["user"] == reading["user"] and
                   (canonical or r["work"] == reading["work"])]
        if matches:
            associations.append([reading["id"], max(matches, key=lambda r: (r["time"], r["id"]))["id"]])
    return dict(works=sorted(group), review_ids=sorted(r["id"] for r in listed if r["status"] == "published"),
                average=str(sum(rated) / len(rated)) if rated else None, ratings_count=len(rated),
                reading_stats=stats, library_users=sorted({r["user"] for r in readings}),
                reading_review_associations=sorted(associations))


def compare(case):
    original = deepcopy(case)
    legacy_group = equivalent_work_ids(SnapshotSession(case["works"]), case["anchor"])
    root = confirmed_root(case["anchor"], case["confirmed"])
    group = {w["id"] for w in case["works"] if confirmed_root(w["id"], case["confirmed"]) == root}
    legacy, proposed = metrics(case, legacy_group), metrics(case, group, canonical=True)
    assert case == original, "Comparison must not mutate its input"
    return dict(scenario=case["name"], legacy=legacy, confirmed_contract=proposed,
                changed_fields=[key for key in legacy if legacy[key] != proposed[key]])


def report():
    return dict(scope="synthetic_only_no_database_no_network",
                legacy_grouping="actual equivalent_work_ids with a read-only session double",
                metrics="test-only oracle of audited semantics, not executed PostgreSQL",
                proposed="confirmed-link contract oracle; no production resolver implemented",
                scenarios=[compare(case) for case in scenarios()])


if __name__ == "__main__":
    import json
    print(json.dumps(report(), ensure_ascii=False, indent=2))
