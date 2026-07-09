# PLAN: Person Record Merge Workflow

## Goal

Build an admin workflow for merging duplicate `Person` records into a preferred surviving person while preserving relationships, crime links, external identifiers, and enough audit history for researchers to understand what happened.

This is needed because early modern records often contain partial, variant, honorific, or ambiguous names. Imports from external researchers can create or reveal duplicate people, and the project needs a safe way to reconcile those identities after review.

## Guiding Principles

- Do not enforce uniqueness on `Person(first_name, last_name)`. Duplicate names can be historically valid.
- Merging should be explicit and researcher-directed, never automatic.
- Prefer preserving evidence over discarding it.
- Preserve all database links from merged records.
- Keep an audit trail of who merged what, when, and why.
- Make the merge reversible in principle through logs, even if not automatically reversible at first.

## Proposed User Workflow

1. Researcher opens Django admin `Person` changelist.
2. Researcher selects two or more suspected duplicate `Person` records.
3. Researcher chooses the admin action: `Merge selected people`.
4. Admin shows a confirmation form with:
   - selected people,
   - counts of linked crimes, witnesses, relationships, and external IDs,
   - radio/select field for the surviving preferred person,
   - optional merge note.
5. Researcher confirms.
6. System transfers all references from duplicate people to the survivor.
7. System preserves non-empty/conflicting field values in the survivor notes or a merge log.
8. System deletes or archives duplicate people.
9. Admin displays a success message summarizing transferred records.

## Data to Transfer

The merge operation must move or reconcile:

- `Crime.victim` (M2M, `related_name="crime_victim"`)
- `Crime.perpetrator` (M2M, `related_name="crime_perpetrator"`)
- `Crime.judge` (FK, `on_delete=SET_NULL`)
- `Witness.name` (FK, `on_delete=SET_NULL`)
- `PersonRelation.from_person`
- `PersonRelation.to_person`
- `ExternalPersonIdentifier.person` (FK, `on_delete=SET_NULL`)
- Any future `PersonName`, `PersonAlias`, or import staging records

### Do not hardcode this list

This list will silently rot. We just added an import-provenance subsystem
(`SourceDataset`, `ImportBatch`, `ExternalPersonIdentifier`) and this plan
anticipates future `PersonName` / `PersonAlias` models. A hardcoded transfer
list will miss any new FK/M2M to `Person` added later, and those links will be
quietly orphaned or dropped at merge time.

Prefer driving transfers off `Person._meta.related_objects` so every reverse
relation is discovered automatically, with an explicit allow/deny list for the
relations that need special handling (notably `PersonRelation`, which is not a
simple reassignment — see below). At minimum, audit `Person`'s reverse
relations before shipping, and re-audit whenever a new `Person` FK/M2M is added.

## Field Preservation Rules

For scalar / text fields on duplicate people:

- If survivor field is blank and duplicate field is filled, copy duplicate value to survivor.
- If survivor field is filled and duplicate field has a different value, preserve the duplicate value in an audit note.
- Never overwrite survivor values silently.

Text/char fields this applies to:

- `first_name`
- `last_name`
- `given_name`
- `honorific`
- `description`
- `occupation`
- `identifying_information`
- `gender`
- `citizenship`
- `nationality_ethnicity`
- `notes`

### `repeat_offender` is a special case

`repeat_offender` is a `BooleanField(default=False)`, not a text field, so the
"copy if survivor is blank" rule does not apply — `False` is a value, not an
empty field. Use **OR** semantics instead: if the survivor OR any duplicate is
a repeat offender, the survivor becomes `True`. Never downgrade a survivor from
`True` to `False`.

Example preserved note:

```text
Merged from Person #123 (Ser Francesco Falier):
- honorific: Ser
- given_name: Francesco Falier
- gender: U
- notes: Imported from Midura subject_id 480.
```

## Relationship Merge Rules

`PersonRelation` needs special handling.

**Watch the related_name inversion.** In the model the FK related_names are
crossed: `from_person` uses `related_name="to_person"` and `to_person` uses
`related_name="from_person"`. So `person.to_person.all()` returns the relations
where `person` is on the *from* side, and `person.from_person.all()` returns the
relations where `person` is on the *to* side. It is very easy to get this
backwards — query both reverse accessors explicitly and test the direction.

When moving relationships:

- If `from_person` or `to_person` is a duplicate, replace it with the survivor.
- If that would create a self-relationship, skip it and record it in the merge
  log. Note this includes the case where the survivor and a duplicate already
  have a relation *between* them — reassigning the duplicate side to the
  survivor collapses it into a self-relation, which the DB check constraint
  (`prevent_self_relationship`) forbids. Skip and log.
- If that would violate the unique `(type, from_person, to_person)` constraint, keep the existing relationship and append notes from the duplicate relationship where useful.
- Preserve relationship notes in the merge log if they cannot be safely merged.

## Audit Model

Add a `PersonMergeLog` model.

Suggested fields:

- `survivor` — FK to `Person`, nullable on delete
- `merged_person_id` — integer snapshot of deleted/archived person ID
- `merged_person_label` — string snapshot of duplicate display name
- `merged_by` — FK to user, nullable
- `merged_at` — datetime
- `note` — researcher-entered note
- `field_summary` — text summary of copied/conflicting fields
- `relationship_summary` — text summary of moved/skipped relationships
- `transfer_summary` — text summary of crime/witness/external ID transfers

This gives us a durable record even if duplicate `Person` rows are deleted.

## Delete vs Archive

Two possible approaches:

### Option A: Delete duplicates

Pros:
- Simpler.
- Keeps person lists clean.
- Easier to implement.

Cons:
- Harder to reverse.
- Requires excellent merge logs.

### Option B: Archive duplicates

Add fields to `Person`:

- `is_archived`
- `merged_into`
- `merged_at`

Pros:
- Safer for scholarship and auditability.
- Easier to inspect/reverse.

Cons:
- Requires filtering archived people out of normal admin choices/searches.
- More UI work.

Recommendation: start with hard delete plus `PersonMergeLog`, unless the research team strongly prefers retaining duplicate rows. If duplicates are deleted, the merge log is required.

## Implementation Steps

1. Add `PersonMergeLog` model and migration.
2. Add merge service/helper function, e.g. `merge_people(survivor, duplicates, user=None, note="")`.
   **The entire body must run inside a single `transaction.atomic()` block**
   (see Atomicity below).
3. Transfer M2M crime links:
   - add survivor to `Crime.victim` / `Crime.perpetrator`,
   - remove duplicates.
4. Transfer FK links:
   - `Crime.judge`,
   - `Witness.name`,
   - `ExternalPersonIdentifier.person`.
5. Reconcile `PersonRelation` rows with self-relationship and uniqueness safeguards.
6. Copy blank survivor fields from duplicates (OR semantics for `repeat_offender`).
7. Preserve conflicting duplicate field values in `PersonMergeLog`.
8. Delete duplicate people. **Must come last** — see ordering note below.
9. Add `PersonAdmin` action and confirmation template.
10. Add tests for each transfer category and edge case.

## Atomicity

The whole merge — every transfer, field copy, log write, and delete — must run
inside one `transaction.atomic()` block. A merge touches many tables across
several models, and with a hard-delete strategy the source rows are gone once
committed. A partial merge (e.g. crashing between transferring witnesses and
deleting the duplicate) would corrupt data irrecoverably. All-or-nothing.

## Transfer-Before-Delete Ordering Is Load-Bearing

`Witness.name`, `Crime.judge`, and `ExternalPersonIdentifier.person` are all
`on_delete=SET_NULL`. If a duplicate `Person` is deleted **before** its
references are reassigned to the survivor, those links do not error — they
silently become `NULL`, and the association is lost with no warning.

This is why delete (step 8) must strictly follow all transfers (steps 3–5).
Do not reorder these steps. The tests should include a case asserting that no
`SET_NULL` link is orphaned after a merge.

## Test Plan

Add tests for:

- victim M2M transfer
- perpetrator M2M transfer
- judge FK transfer
- witness FK transfer
- external person identifier transfer
- basic field fill from duplicate to survivor
- `repeat_offender` OR semantics (True survivor never downgraded; True duplicate promotes survivor)
- conflicting field values recorded in merge log
- duplicate relationship collapse
- self-relationship skip (including survivor↔duplicate existing relation)
- duplicate person deletion
- no `SET_NULL` link (witness / judge / external ID) is orphaned after merge
- merge is atomic — a forced failure mid-merge rolls back all changes
- admin action confirmation path

## Resolved Decisions

- **Delete vs archive:** hard-delete duplicates plus a required `PersonMergeLog`
  for the first iteration. Full archival workflow deferred.
- **Permissions:** allow all staff editors (the editor group from migration
  0018), matching the existing weapon-merge action, which is not superuser-gated.
  Flagged for research-team confirmation before build, but this is the default.

## Open Questions

- Should merge logs appear inline on the survivor `Person` admin page?
- Should we add a separate `PersonAlias` / `PersonName` model before or after merge tooling?
- Should external identifiers be displayed prominently on `Person` admin pages?

## Recommended First Iteration

Implement:

- `PersonMergeLog`
- hard-delete duplicate people after transfer
- `PersonAdmin` merge action with preferred survivor selector
- careful relationship reconciliation
- tests for all transfer paths

Defer:

- full archival duplicate workflow,
- automatic candidate detection,
- alias/name-evidence model,
- undo UI.
