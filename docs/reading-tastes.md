# Mis gustos

Declared reading experiences are independent from favorite genres, narrative
tropes and computed reading statistics. No preference is inferred from books,
reviews or existing selections. Recommendations and ETL do not consume these fields.

## Storage and migration

`0046_reading_tastes` creates four tables in `app`:

- `catalogo_intensidades`: ten stable category IDs, Lucide icon key, semantic
  color key, five level descriptions, ordering and active flag.
- `gustos_intensidades`: account/category primary key, level and position.
- `catalogo_intereses`: ten independent interests in four groups.
- `gustos_intereses`: account/interest primary key.

Levels and positions have checks for 1–5, and positions are unique per account.
The `gustos_intensidades_limit` trigger additionally counts categories, locking
the parent account row before checking; the total limit does not rely only on
position uniqueness. Zero selections are valid. Interests do not consume slots.

Migration preflight refuses conflicting table names. Existing preference tables
and biography are untouched. Apply only after confirming the target environment;
the implementation was migrated and tested on local development PostgreSQL.
Downgrade removes only the four new tables and their function, including their
new saved data; it must not be used to preserve newly collected tastes.

## Existing API extensions

All paths have the usual `/api` prefix and require authentication:

- `GET /profiles/preference-catalogs`: adds `intensities` and `interests` catalogs.
- `GET /profiles/me/literary-preferences`: includes saved category metadata,
  descriptions and levels in user-selected order, plus interests.
- `PATCH /profiles/me/literary-preferences`: accepts an ordered `intensities`
  array of `{category_id, level}` and `interest_ids`. Level must be a strict
  integer from 1 through 5. At most five unique category IDs are accepted.
- `GET /profiles/{profile_id}`: exposes these same declared tastes as public
  profile fields to other authenticated readers, without account/private data.

The writer always uses the session account; arbitrary owner IDs are rejected.
Omitted fields are unchanged, `[]` clears that selection, and explicit `null`
is rejected. All fields in one PATCH commit or roll back together. Saved retired
catalog options may be retained or removed but cannot be newly selected.

## Frontend

`ProfileReadingTastesCard` is shared by own and community `ProfileAboutSection`.
The existing hook/service handles persistence. Radio inputs overlay Lucide icons
for direct click/touch selection and native keyboard navigation; every level has
an accessible label and a visible description. Up/down controls reorder the draft,
and removal frees a slot for replacement. Save confirms and Cancel discards drafts.
Interests use grouped, accent-insensitive search and selectable tags.

The card uses existing theme variables and no additional dependencies. Editor
lists have bounded height; its read-only view shows only the optionally featured category.

## Verification

Run from `apps/backend` with development/test PostgreSQL at migration head:

```powershell
./.venv/Scripts/python.exe -m unittest tests.test_reading_tastes tests.test_literary_preferences tests.test_reading_genres tests.test_user_roles tests.test_post_interactions
```

The PostgreSQL integration suite uses rollback transactions. In particular it
temporarily removes position checks inside a DDL savepoint to demonstrate that
the independent count trigger rejects a sixth category. Other tests cover strict
levels, duplicates, ordering/replacement, independent interests, partial PATCH,
clearing, public projection, owner authorization and rollback on save failure.

Browser verification used the real app/API with temporary PostgreSQL accounts
inside an outer rollback transaction. It covered reload persistence, direct icon
selection, order, replacement, grouped search, cancellation, error/retry states,
clearing all, community read-only access, and six themes at 1440/768/390px widths.
Temporary fixtures and test accounts were removed afterward.


## One visible indicator in Sobre mí

Migration `0047_featured_reading_taste` adds `featured` (default false) to the
existing selected-intensity relation. A partial unique index on `user_id WHERE
featured` ensures at most one highlighted category per account. There is no
additional table or copied intensity value; deleting the selected row also
removes its featured status. Existing ratings are preserved and none are
highlighted automatically.

The existing own/public preference responses add `featured_category_id`.
PATCH accepts that ID only if it belongs to the resulting selected categories;
explicit `null` clears it and omission preserves it while the category remains
selected. Removing the category clears it automatically. Transactions and
session ownership are unchanged.

In Sobre mí, `ProfileReadingTastesCard` displays exactly one indicator, or an
empty state when none is highlighted. Its existing editor still loads all saved
ratings (maximum five), with a star toggle labelled “Mostrar en Sobre mí”.
Selecting a different star replaces the previous choice; deselecting allows
none. Other interests retain their existing tags and persistence.
The community About view uses the same read-only rendering. No highlighted
indicator is added to Mi actividad or to the profile header. No quote collection,
illustrations or mockup sample data were added.

`test_featured_taste.py` covers optional selection, switching, clearing, omitted
fields, updated levels, category removal, rollback, ownership and rejection of
a second feature by PostgreSQL. Browser checks against transactional PostgreSQL
accounts verified five editor ratings but one visible indicator, reload,
removal/replacement, public read-only access, six themes and 1440/768/390px
layouts. The complete backend suite passed 49 tests; test data was rolled back.
