# Import and data-model audit

Date: 2026-08-10
Branch: `codex/import-pipeline-consistency`

## Executive summary

The import pipeline can support the supplied Padua and Midura/Venice files at their current size without a server-side timeout, and the new canonical template gives researchers a stable starting point. The largest remaining risk is silent data loss: several source files contain populated columns that are not mapped into the database, and blank-headed columns are currently discarded even when they contain values.

The next round of work should therefore focus on validation and schema policy, not additional header aliases. The importer should identify every populated, unmapped column before preview, distinguish warnings from blocking errors, and make the import/export contract explicitly round-trip safe.

## Work completed on this branch

- Changed import identity from source case number to the database primary key, shown as `Database ID`.
- Made `Crime.number` optional and non-unique; new imports no longer generate `AUTO_*` values.
- Added durable import-batch auditing, counts, hashes, and rollback of records created by a batch.
- Added early header normalization and source-specific import profiles.
- Added caches for repeated person, weapon, city, and location resolution.
- Omitted expensive per-cell HTML diffs for files over 500 rows while retaining parsing and validation.
- Added an authenticated Import Guide and a generated, header-only canonical CSV template to Django admin.

## Import contract

`Database ID` is the only update key. A blank value creates a new record, an existing value updates that database record, and an unknown value is an error. `Number` is source metadata: it may be blank or repeated and is not used to determine record identity.

The downloadable template is generated from `CrimeResource`, so its headers track the active import resource rather than a separately maintained static file. The guide also lists accepted legacy aliases and explains preview, confirmation, large-file behavior, and rollback limitations.

## Supplied-file audit

All five files in `static-data/` were profiled by logical CSV/TSV rows and by the number of nonblank cells in columns that the active importer does not consume.

| Source | Data rows | Populated columns not imported | Notes |
| --- | ---: | --- | --- |
| Midura/Venice TSV | 1,712 | None after the source profile | Uses the `Sentence_Enforced` alias and source-specific `subject_ids`; `Input by` is intentionally replaced by the logged-in importer. |
| Padua CSV | 1,850 | None | `Case Number` is recognized but entirely blank. |
| `master-data.csv` | 21 | `Date of document` (18), `Festival` (1), `Date of Entry` (1), `Link to Photo` (18) | `Long_Latitude` is present but empty; ten trailing blank headers are empty. |
| `modena-data.csv` | 280 | `Victim_Father` (73), `Citizenship` (13), `Assailant_Occupation` (32), `office holder` (1) | Other legacy columns are present but empty. |
| `rose_data.csv` | 699 | `Researcher_Notes` (277), blank header column 20 (123), blank header column 21 (558) | The unnamed columns contain substantive values, including narrative notes, image references, and time-like values. They are currently dropped without a warning. |

These counts measure populated cells, not necessarily unique records or fields that should all become permanent model columns. They establish that the current importer can discard source information without telling the user.

## Import/export symmetry

The public CSV export is not currently a safe canonical re-import format.

- It exports both `Description_of_Location` from `Location.description_of_location` and `Description of Location` from `Crime.description_of_location`.
- Header normalization aliases `Description_of_Location` to `Description of Location`; when both exist, the canonical name wins. Re-import can therefore collapse two different concepts into one value or construct the wrong location.
- Several current domain fields are not covered consistently by the canonical import/export resource, including offense category, sentence in absentia, historical date, liturgical occasion, sestiere, pardon, accord and accord date, judge, and source.
- Some omissions may be intentional workflow or internal fields, but there is no documented inclusion policy or round-trip test defining which omissions are safe.

The application should define one canonical schema for admin import, admin export, and public export, with source-specific adapters feeding into it. Human-friendly public exports can be separate, but they should not look like re-importable templates unless they are tested as such.

## Model and write-path audit

### Dates

The Django admin derives `year`, `month`, `day`, and `day_of_week` from an exact `date` in `CrimeAdmin.save_model`. The import resource does not apply the same rule. In the local database snapshot, 522 crimes have an exact date but no year, and 300 have at least one date component inconsistent with the exact date. Date normalization should live in a shared model/service boundary and existing records should be audited and backfilled deliberately.

### User deletion behavior

`Crime.input_by` and `Crime.updated_by` use `CASCADE`, unlike `assigned_to`, which uses `SET_NULL`. Deleting a user can consequently delete crime records they created or last updated. Historical attribution should normally be nullable metadata, not ownership of the historical record.

### Entity resolution

Canonical person resolution relies on exact, case-sensitive first/last-name matching and does not surface ambiguous existing matches. The local database has 40 exact duplicate person-name groups covering 82 records. It also contains five normalized duplicate weapon-name groups and eight normalized duplicate city-name groups. These are not all necessarily erroneous—historical people may share names—but the system needs explicit match confidence, provenance, and a review workflow rather than silent reuse.

### Controlled values

Boolean imports currently reduce values to true only for `Y`/`YES`; blank, `N`, unknown, and typo values all become false in non-nullable fields. Gender cleanup takes the first letter of any supplied string without validating it against model choices. Invalid or ambiguous source values should be reported during preview rather than silently coerced.

### Relationship natural keys

`PersonRelationTypeManager.get_by_natural_key()` queries `name_en`, but `PersonRelationType` defines `name`. Natural-key deserialization will fail if this manager path is used.

### Location identity

Location uniqueness is conditional on both category and description being populated. In the local snapshot, 512 of 662 locations have both fields blank. This makes source normalization and review more important because database constraints cannot provide a strong natural identity for most locations.

## Local database snapshot

The audit used a read-only aggregate scan of the developer database:

| Check | Result |
| --- | ---: |
| Crime records | 1,420 |
| Existing `AUTO_*` numbers | 0 |
| Blank/null crime numbers | 0 |
| Duplicate nonblank crime numbers | 0 groups |
| Exact dates without year | 522 |
| Exact-date/component mismatches | 300 |
| Person records | 2,401 |
| Exact duplicate person-name groups | 40 groups / 82 records |
| Weapon records | 262 |
| Normalized duplicate weapon-name groups | 5 groups / 10 records |
| City records | 525 |
| Normalized duplicate city-name groups | 8 groups / 16 records |
| Location records | 662 |
| Locations with blank category and description | 512 |
| Import batches | 0 |
| External person identifiers | 0 |
| Person relations | 0 |

These figures describe the local snapshot only; they are evidence for prioritization, not a production migration plan.

## Performance and timeout assessment

The original admin timeout risk was primarily the cost of rendering row-by-row HTML diffs plus repeated lookup queries. With lookup caches and diff omission above 500 rows, local dry runs completed with zero row errors in approximately 4.6 seconds for the 1,850-row Padua CSV and 10.4 seconds for the grouped 1,465-row Midura import profile. All five supplied datasets completed dry-run validation without row errors.

This substantially lowers application-side timeout risk for files of the supplied size. Production should still log import duration, row count, query count where practical, and worker/request timeout failures. Very large imports may eventually belong in a background job, but the current evidence does not justify adding that infrastructure yet.

## Priorities

1. [#84: Block imports that would discard populated unknown columns](https://github.com/chnm/mv-django/issues/84).
2. [#85: Define and test a round-trip-safe canonical CSV schema](https://github.com/chnm/mv-django/issues/85).
3. [#86: Prevent user deletion from cascading to Crime records](https://github.com/chnm/mv-django/issues/86).
4. [#87: Centralize Crime date derivation and repair inconsistent components](https://github.com/chnm/mv-django/issues/87).
5. [#88: Add ambiguity reporting and review tools for imported entities](https://github.com/chnm/mv-django/issues/88).
6. [#89: Validate controlled and tri-state values during import preview](https://github.com/chnm/mv-django/issues/89).
7. [#90: Fix `PersonRelationType` natural-key lookup](https://github.com/chnm/mv-django/issues/90).

## Limitations

- The profile describes the files currently present in `static-data/`; future spreadsheets will introduce new variants.
- Source-column counts do not decide the final domain model. Some values may belong in structured fields, related models, attachments, or preserved raw-import metadata.
- The local database may differ from production.
- Import rollback intentionally deletes only records created by that batch; it does not reverse updates to pre-existing records.
