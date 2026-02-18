# SPEC.md

> For technical implementation details, architecture, and developer documentation, see [AGENTS.md](./AGENTS.md).

---

## Table of Contents

- [Overview](#overview)
- [Users & Roles](#users--roles)
- [Business Rules](#business-rules)
- [Features](#features)
- [User Flows](#user-flows)
  - [Flow 1: Browsing the Interactive Map](#flow-1-browsing-the-interactive-map)
  - [Flow 2: Entering a Crime Record via Admin](#flow-2-entering-a-crime-record-via-admin)
  - [Flow 3: Bulk Importing Crime Data via CSV](#flow-3-bulk-importing-crime-data-via-csv)
- [Out of Scope](#out-of-scope)
- [Open Questions](#open-questions)

---

## Overview

**Mapping Violence** is a digital humanities research database and public-facing application for documenting, analyzing, and visualizing patterns of interpersonal violence in early modern Italy, with a primary focus on Venice and surrounding regions in the 16th and 17th centuries.

The project digitizes archival records (court documents, criminal registers) into a structured relational database that links violent events to the people, places, weapons, and legal proceedings involved. The dataset supports both qualitative scholarly research and quantitative spatial/temporal analysis.

**Core value:** Allow historians to ask questions about who committed violence, against whom, where, with what weapons, and with what legal consequences — and to explore those patterns spatially on a map.

**Target audiences:**
- Research team members entering and curating archival data
- Academic scholars exploring the public-facing data table and map
- Students and general audiences engaging with project narrative content

---

## Users & Roles

### Superuser / Administrator
- Full access to all data via Django admin (`/admin/`) and Wagtail CMS (`/cms/`)
- Can create and manage other user accounts (invite-only — no self-registration)
- Can import/export CSV data, manage all records, and configure site content
- Typical persona: project PI or lead developer

### Research Team Member (Staff)
- Django staff account; access to `/admin/` for data entry and editing
- Can create, edit, and delete Crime, Person, Location, Weapon, and Event records
- Can import data via CSV; can export filtered record sets
- Cannot manage other user accounts or modify CMS content (unless granted)
- Typical persona: graduate research assistant or postdoctoral fellow

### Public Visitor (Anonymous)
- Read-only access to the public website
- Can browse the interactive map, filter the crime data table, and read project content pages
- Cannot access admin, CMS, or any write operations
- No login required

| Action | Superuser | Staff | Public |
|--------|-----------|-------|--------|
| View map and crime table | ✓ | ✓ | ✓ |
| View crime detail pages | ✓ | ✓ | ✓ |
| Enter/edit crime records | ✓ | ✓ | ✗ |
| Import CSV data | ✓ | ✓ | ✗ |
| Export data | ✓ | ✓ | ✗ |
| Manage user accounts | ✓ | ✗ | ✗ |
| Edit CMS content pages | ✓ | ✗ | ✗ |

---

## Business Rules

### Crime Records

- A Crime record represents a single violence event documented in archival sources
- `number` is the archival case identifier (e.g., `"ABC-001"`); not required to be unique at the DB level but should be unique in practice
- `crime` is a free-text modern taxonomy label (e.g., "assault", "homicide"); `offense_category` is a controlled vocabulary parallel field
- A Crime can have multiple victims and multiple perpetrators (M2M to Person)
- `fatality` = True means the victim died as a result of the crime
- Both `date` (standard date) and `historical_date` (EDTF uncertain date) may be populated; they are parallel fields for the same event, not redundant
- `year`, `month`, `day`, `day_of_week` are discrete fields derived from `date` for querying convenience; they are not auto-computed — enter manually or via import

### Person Records

- A Person record can appear as victim, perpetrator, witness, and/or judge across different crimes
- Name format convention: `last_name, first_name` (used by `__str__` and import widgets)
- `gender` choices: `M` (Male), `F` (Female), `U` (Unknown/Unrecorded) — default `U` when not in source
- `nationality_ethnicity` is populated only when explicitly recorded in the archival source
- Person-to-Person relationships use a controlled vocabulary (`PersonRelationType`) with optional inverse relationship types (e.g., "Parent" ↔ "Child")
- A Person cannot have a relationship with themselves (DB constraint)
- Each (from_person, to_person, relation_type) triple must be unique (DB constraint)

### Location Records

- Each Location belongs to a City
- If a Location has no specific coordinates, `effective_latitude` / `effective_longitude` fall back to the parent City's coordinates — this is intentional for records where only the city is known
- `category_of_space` classifies the type of space (sacred, public, domestic, etc.) using a controlled vocabulary
- Location uniqueness is enforced on the combination of `(city, category_of_space, description_of_location)`

### Weapon Records

- Weapons have a two-level classification: `weapon_category` (controlled: firearm, blade, blunt_instrument, hands, other) and `weapon_subcategory` (free text, e.g., "sword", "dagger")
- The legacy `category` FK to `WeaponCategory` model coexists with the newer choice-based fields; prefer `weapon_category` for new data entry

### Data Entry

- `Crime.input_by` and `Crime.updated_by` are automatically set from `request.user` on save; they are not editable in the admin form
- All fields with user-facing help text display that text in the admin to guide data entry
- Fields are generally optional (`blank=True`) to support incremental data entry from incomplete archival sources

### Import / Export

- CSV import matches People by `"Last, First"` name format; creates new Person records if no match found
- CSV import matches Weapons by name; creates new Weapon records if no match found
- CSV import matches City and Location by name with `get_or_create` logic
- Exported CSV reflects the same field mapping as import; suitable for round-trip editing

---

## Features

### Feature: Interactive Violence Map

**Description:**
A full-page Leaflet map showing all recorded crime locations, with filtering and color-by visualization options.

**Functionality:**
- Circle markers at each Location; default size scaled to crime count at that location
- Filter panel (collapsible via header caret) with controls for: City, Crime Type, Weapon Category, Year From, Year To
- Color-by modes: None (default amber), Crime Type (categorical palette), Fatal/Non-fatal (red/green), Gender (blue/pink/gray) with victim or perpetrator sub-option
- In color-by mode, individual crime markers are rendered with jitter when multiple crimes share a location
- A legend appears bottom-left when any color-by mode is active
- All filter and color-by state is encoded in the URL query string (survives reload and sharing)
- Empty-state message displayed over the map when filters return no results
- Clicking a marker opens a sliding drawer with location details and a list of crimes at that location
- Each crime in the drawer links to its detail page; crime type label links to the filtered data table

### Feature: Crime Data Table

**Description:**
A paginated, filterable table of all crime records at `/data/`.

**Functionality:**
- Filter by: case number (text search), crime type (select), city (select), person name (searches both victim and perpetrator), year (text), fatality (boolean), weapon category (select), weapon subcategory (text search)
- 50 records per page; sortable columns
- Table columns: Case Number (links to detail), Crime Type, Date, City, Victims, Perpetrators, Fatality
- Apply Filters / Reset Filters button is context-sensitive: shows Apply when no active filters, Reset when filters are present
- Case number cell links to `/crime/<id>/`

### Feature: Crime Detail Page

**Description:**
A structured display of a single crime record at `/crime/<id>/`.

**Functionality:**
- Header shows case number, crime type (as a link to filtered table), and date
- Sections: Location, People Involved (victims, perpetrators, judge), Crime Details (weapon, description), Legal Information (court, classification, trial phase), Sentencing (sentence, in absentia, sentence enforced, pardoned, convicted)
- Layout uses a two-column grid for Legal Information and Sentencing sections

### Feature: Admin Data Entry

**Description:**
Django Unfold admin at `/admin/` for structured data entry and management.

**Functionality:**
- `CrimeAdmin`: full fieldsets covering all Crime fields; WitnessInline for testimony records; autocomplete for Person M2M fields; CSV import/export
- `PersonAdmin`: displays PersonRelation inlines for both directions of relationships; grouped by relationship category
- `LocationAdmin`: shows effective coordinates; collapsible sections for address components
- `WeaponAdmin`: fieldsets separating basic info from classification
- All admins have `list_display`, `list_filter`, `search_fields` configured

### Feature: CMS Content Pages

**Description:**
Wagtail-powered narrative content at `/cms/` for project team to manage.

**Functionality:**
- Home page content (`HomePageContent` snippet): title, lede, main body — one active at a time
- Team page (`ProjectPerson` snippets): name, role, university, bio, photo — grouped into "project team" and "advisory board" display order
- `GeneralPage`: StreamField pages for any other project content (paragraphs, image galleries)
- Wagtail handles page hierarchy and URL routing for general pages

---

## User Flows

### Flow 1: Browsing the Interactive Map

**Goal:** A scholar wants to explore where violence occurred in Venice and understand patterns by crime type.

**Starting Point:** Visitor navigates to `/map/`

**Steps:**

1. Map loads centered on Italy at zoom level 7
   - Default amber circle markers appear at all locations with recorded crimes
   - Filter panel visible in top-right corner (expandable/collapsible via header)
   - No color-by mode active

2. Visitor opens filter panel and selects a city (e.g., "Venice")
   - Clicks "Apply Filters"
   - URL updates with `?city=<id>` parameter
   - Map reloads with only Venice locations

3. Visitor selects "Color by: Crime Type" from the Visualization dropdown
   - Markers re-render with individual colors per crime type
   - Jittered individual markers appear when multiple crimes share a location
   - Legend appears bottom-left showing color → crime type mapping

4. Visitor clicks a marker
   - Sliding drawer opens from the left
   - Shows location name, city, and list of crimes at that location
   - Each crime shows case number (links to detail page) and crime type (links to filtered table)

5. Visitor clicks a crime type label in the drawer
   - Navigates to `/data/?crime=assault` (filtered crime table)

**Success Outcome:** Visitor can spatially explore crimes and drill into individual records.

**Error Path:** Filters return no results → empty-state overlay appears: "No violence events match the current filters."

---

### Flow 2: Entering a Crime Record via Admin

**Goal:** A research assistant documents a newly transcribed archival record.

**Starting Point:** Staff member navigates to `/admin/mapping_violence/crime/add/`

**Steps:**

1. Enter case identification
   - `number`: archival case ID
   - `crime`: crime type (free text)
   - `offense_category`: select from controlled vocabulary

2. Enter people involved
   - `victim`: autocomplete search — type last name, select or create Person
   - `perpetrator`: same as victim
   - `judge`: FK autocomplete

3. Enter location
   - `location`: FK to Location — search by name; Location must already exist

4. Enter date information
   - `date`: standard date if known exactly
   - `historical_date`: FK to a HistoricalDate if date is uncertain/approximate
   - `year`, `month`, `day`: enter discrete values manually

5. Enter legal outcome
   - `fatality`: check if victim died
   - `convicted`, `pardoned`, `sentence`, `sentence_in_absentia`: fill as known

6. Save record
   - `input_by` auto-populated with current user
   - Record appears in crime table and on map

**Error Paths:**
- Required Person doesn't exist: must first create Person record, then return
- Duplicate case number: no DB constraint prevents duplicates; researcher must check manually

---

### Flow 3: Bulk Importing Crime Data via CSV

**Goal:** A researcher imports a batch of pre-formatted archival records.

**Starting Point:** Staff member navigates to `/admin/mapping_violence/crime/` → "Import" button

**Steps:**

1. Download the export format (optional) to understand expected column names

2. Prepare CSV with columns matching the CrimeResource field mapping
   - Person fields: `"Last, First"` format
   - Location: city name + location name
   - Dates: ISO format where possible

3. Upload CSV via the Import form; select CSV format

4. Review the preview (dry-run) — shows rows that will be created/updated and any errors

5. Confirm import
   - `PersonWidget` resolves people by name, creates new Person records as needed
   - `WeaponWidget` resolves weapons by name, creates new Weapon records as needed
   - `LocationWidget` resolves by city + location name

6. Verify imported records in the crime table

**Error Paths:**
- Malformed CSV: import halts with error on the offending row
- Unknown location that can't be resolved: row skipped or flagged depending on widget behavior
- Duplicate records: django-import-export uses `skip_unchanged=True` by default; existing records with matching key fields are updated, not duplicated

---

## Out of Scope

### Not in current version (potential future work)
- Real-time collaborative data entry
- Public user accounts or saved searches
- Network graph visualization of person relationships
- Timeline/temporal visualization beyond the map
- API access with authentication tokens for external data consumers
- Mobile-optimized native app

### Explicitly excluded
- PostGIS / spatial queries — geographic data is stored as decimal coordinates only; spatial operations are not required for current research questions
- Full-text search engine (Elasticsearch, Meilisearch) — ORM `icontains` is sufficient for current dataset scale
- Payment processing — the project is grant-funded, not a commercial product
- Offline mode — not applicable for a web-based research database

---

## Open Questions

### Data Model
- **Q:** Should `Crime.year/month/day` be auto-computed from `Crime.date` on save rather than entered manually?
  - **Context:** Currently entered separately, creating risk of inconsistency. Auto-computation would eliminate data entry error but may conflict with cases where year is known but full date is not.
  - **Options:** Auto-populate from `date` if `year` is blank; always auto-compute; keep manual
  - **Owner:** Research team + dev
  - **Status:** Open

- **Q:** Should `Crime.crime` (free-text type) be converted to a FK or controlled vocabulary?
  - **Context:** Currently free text with a `TODO` comment in the model. Inconsistent entries exist in the data. `offense_category` was added as a parallel controlled field but doesn't fully replace it.
  - **Options:** Controlled vocab model + migration; keep free text with normalization; use `offense_category` exclusively
  - **Owner:** PI + research team
  - **Status:** Open

### Features
- **Q:** Should the map support clustering for dense location areas?
  - **Context:** When many crimes share nearby locations, individual jittered markers may overlap. Clustering was explicitly kept off in the current design to maintain individual clickability.
  - **Owner:** PI
  - **Status:** Decided against for now; revisit if dataset grows significantly

### Data Entry
- **Q:** What is the canonical import CSV format and where should it be documented?
  - **Context:** `static-data/` contains source CSVs but no import template or data dictionary exists in the repo. New research assistants have no guide.
  - **Options:** Add `static-data/README.md` with field mapping; add example template CSV; document in admin help text
  - **Owner:** Dev + research team
  - **Status:** Open

---

*Last Updated: 2026-02-18*
*This document is maintained for AI agent context and onboarding.*
