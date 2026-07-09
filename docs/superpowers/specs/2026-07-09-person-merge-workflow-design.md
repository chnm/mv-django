# Design: Person Record Merge Workflow + Alias Evidence

**Date:** 2026-07-09
**Status:** Approved design, ready for implementation planning

## Goal

Build an admin workflow for merging duplicate `Person` records into a preferred
surviving person while preserving relationships, crime links, external
identifiers, name-variant evidence, and enough audit history for researchers to
understand what happened.

This is needed because early modern records often contain partial, variant,
honorific, or ambiguous names. Imports from external researchers can create or
reveal duplicate people, and the project needs a safe way to reconcile those
identities after review.

## Guiding Principles

- Do not enforce uniqueness on `Person(first_name, last_name)`. Duplicate names
  can be historically valid.
- Merging is explicit and researcher-directed, never automatic.
- Prefer preserving evidence over discarding it. Name variants become
  first-class `PersonAlias` records, not just log text.
- Preserve all database links from merged records.
- Keep an audit trail of who merged what, when, and why.
- Make the merge reversible in principle through logs, even if not
  automatically reversible at first.

## Scope Decisions (Resolved)

- **Delete vs archive:** hard-delete duplicates plus a required `PersonMergeLog`.
  Full archival workflow deferred.
- **Alias model:** in scope for this iteration. Name variants are captured as
  `PersonAlias` records rather than log text.
- **Permissions:** the merge action is available to all staff editors (the
  editor group from migration 0018), matching the existing weapon-merge action,
  which is not superuser-gated. Flagged for research-team confirmation, but this
  is the default.
- **Admin display:** aliases, external identifiers, and merge logs all appear as
  inlines on the Person change page.

## New Models

### `PersonAlias`

Captures a name variant as evidence.

| Field | Type | Notes |
|-------|------|-------|
| `person` | FK → `Person` | `on_delete=CASCADE`, `related_name="aliases"` |
| `name` | `CharField(max_length=500)` | the variant as written, e.g. "Ser Francesco Falier" |
| `source_dataset` | FK → `SourceDataset` | nullable, `on_delete=SET_NULL` — provenance |
| `origin_person_id` | `IntegerField` | nullable — snapshot of the merged person id this came from |
| `note` | `TextField(blank=True)` | |

- Unique constraint on `(person, name)` to avoid redundant rows.
- Single display-string representation (not structured first/last/given
  fields) — captures the variant as researchers actually wrote it.

### `PersonMergeLog`

Durable audit record that survives hard-deletion of duplicate `Person` rows.

| Field | Type | Notes |
|-------|------|-------|
| `survivor` | FK → `Person` | nullable on delete |
| `merged_person_id` | `IntegerField` | snapshot of deleted person id |
| `merged_person_label` | `CharField` | snapshot of duplicate display name (`str(person)`) |
| `merged_by` | FK → user | nullable |
| `merged_at` | `DateTimeField` | |
| `note` | `TextField` | researcher-entered note |
| `field_summary` | `TextField` | copied/conflicting scalar fields |
| `relationship_summary` | `TextField` | moved/skipped relationships |
| `transfer_summary` | `TextField` | crime/witness/external-ID transfers |
| `alias_summary` | `TextField` | name variants captured as aliases |

## Merge Service

`merge_people(survivor, duplicates, user=None, note="")` — the whole body runs
inside a single `transaction.atomic()` block.

### Atomicity

A merge touches many tables across several models, and with hard-delete the
source rows are gone once committed. A partial merge (e.g. crashing between
transferring witnesses and deleting the duplicate) would corrupt data
irrecoverably. All-or-nothing.

### Execution order (load-bearing)

1. Transfer M2M crime links: add survivor to `Crime.victim` / `Crime.perpetrator`, remove duplicates.
2. Transfer FK links: `Crime.judge`, `Witness.name`, `ExternalPersonIdentifier.person`.
3. Reconcile `PersonRelation` rows (see rules below).
4. Capture aliases (see below).
5. Copy blank survivor fields from duplicates (OR semantics for `repeat_offender`).
6. Write `PersonMergeLog`.
7. Delete duplicate people — **must be last**.

**Why delete is last.** `Witness.name`, `Crime.judge`, and
`ExternalPersonIdentifier.person` are `on_delete=SET_NULL`; `PersonAlias.person`
and `PersonRelation.from/to_person` are `on_delete=CASCADE`. Deleting a
duplicate before its references are reassigned would either silently NULL the
links (SET_NULL) or cascade-delete the evidence (CASCADE) — no error, just data
loss. Every transfer/reassignment must complete before any delete.

### Transfer completeness

Drive reassignment off `Person._meta.related_objects` with an explicit
special-case list (`PersonRelation`, `PersonAlias`) rather than a hardcoded
field list, so future `Person` FK/M2M relations are not silently missed. The
import-provenance subsystem (`SourceDataset`, `ImportBatch`,
`ExternalPersonIdentifier`) was recently added; a hardcoded list would already
be at risk of drifting. Re-audit reverse relations before shipping and whenever
a new `Person` relation is added.

## Field Preservation Rules

For scalar / text fields on duplicate people:

- If survivor field is blank and duplicate field is filled, copy duplicate value
  to survivor.
- If survivor field is filled and duplicate field has a different value,
  preserve the duplicate value in `PersonMergeLog.field_summary`.
- Never overwrite survivor values silently.

Text/char fields this applies to: `first_name`, `last_name`, `given_name`,
`honorific`, `description`, `occupation`, `identifying_information`, `gender`,
`citizenship`, `nationality_ethnicity`, `notes`.

**`repeat_offender` is a special case.** It is a `BooleanField(default=False)`,
so "copy if blank" does not apply — `False` is a value, not empty. Use OR
semantics: if the survivor OR any duplicate is a repeat offender, the survivor
becomes `True`. Never downgrade a survivor from `True` to `False`.

## Alias Capture on Merge

For each duplicate:

- Mint one `PersonAlias` on the survivor from the duplicate's full display name
  (`str(dup)`), stamping `origin_person_id` and (if known) `source_dataset`.
- Re-point the duplicate's existing `PersonAlias` records to the survivor.
- De-duplicate against the survivor's current display name and existing aliases
  (via the `(person, name)` unique constraint) so nothing redundant is stored.

Because `PersonAlias.person` is `CASCADE`, existing aliases MUST be reassigned
before the duplicate is deleted, or they will be cascade-deleted.

Record a summary of captured/transferred aliases in
`PersonMergeLog.alias_summary`.

## Relationship Merge Rules

`PersonRelation` needs special handling.

**related_name inversion warning.** The FK related_names are crossed:
`from_person` uses `related_name="to_person"` and `to_person` uses
`related_name="from_person"`. So `person.to_person.all()` returns relations
where `person` is the *from* side, and `person.from_person.all()` returns
relations where `person` is the *to* side. Query both reverse accessors
explicitly and test the direction.

When moving relationships:

- If `from_person` or `to_person` is a duplicate, replace it with the survivor.
- If that would create a self-relationship, skip it and record it in the merge
  log. This includes the case where the survivor and a duplicate already have a
  relation *between* them — reassigning collapses it into a self-relation, which
  the DB check constraint (`prevent_self_relationship`) forbids.
- If that would violate the unique `(type, from_person, to_person)` constraint,
  keep the existing relationship and append notes from the duplicate relationship
  where useful.
- Preserve relationship notes in the merge log if they cannot be safely merged.

## Admin

`PersonAdmin` ([admin.py:779](../../../mapping_violence/admin.py)) gains:

- **Merge action** — `merge_people` admin action with a confirmation form and
  template, modeled on the existing `merge_weapons` action
  ([admin.py:859](../../../mapping_violence/admin.py)). A `ModelChoiceField`
  with `RadioSelect` selects the surviving preferred person; an optional merge
  note is captured. Requires at least two selected people. Staff-editor
  accessible.
- **Inlines on the Person change page:**
  - `PersonAlias` — editable inline (researchers can add/edit variants directly).
  - `ExternalPersonIdentifier` — read-mostly inline showing source provenance,
    visible during merge review.
  - `PersonMergeLog` — read-only inline showing merge history for the survivor.

### Confirmation flow

1. Researcher selects two or more suspected duplicates in the Person changelist.
2. Chooses the `Merge selected people` action.
3. Confirmation form shows: selected people; counts of linked crimes, witnesses,
   relationships, aliases, and external IDs; radio selector for the surviving
   person; optional merge note.
4. On confirm, `merge_people` runs and a success message summarizes transferred
   records.

## Test Plan

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
- alias minted per duplicate from display name
- existing duplicate aliases reassigned to survivor (not orphaned by CASCADE delete)
- alias de-duplication against survivor name / existing aliases
- no `SET_NULL` link (witness / judge / external ID) orphaned after merge
- merge is atomic — a forced failure mid-merge rolls back all changes
- duplicate person deletion
- admin action confirmation path
- Person admin inlines render (alias / external ID / merge log)

## Implementation Order

1. Add `PersonAlias` and `PersonMergeLog` models + migration.
2. Add `merge_people()` service with `transaction.atomic()`.
3. Implement transfers (M2M, FK, relations) driven off `_meta.related_objects`
   with special-cased `PersonRelation` / `PersonAlias`.
4. Implement alias capture.
5. Implement field preservation (incl. `repeat_offender` OR).
6. Write `PersonMergeLog`.
7. Delete duplicates.
8. Add `PersonAdmin` merge action + confirmation template.
9. Add Person admin inlines.
10. Tests for every category above.

## Deferred

- Full archival duplicate workflow (`is_archived` / `merged_into`).
- Automatic duplicate-candidate detection.
- Undo UI (logs support manual reconstruction only).
