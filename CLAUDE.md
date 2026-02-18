# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All Python commands run through `uv run`. All make targets are wrappers around these.

```bash
# Development server
make preview                        # uv run manage.py runserver

# Code quality (run before committing — pre-commit hooks enforce these)
uv run ruff check .                 # lint
uv run ruff format .                # format Python
uv run djhtml <file>                # format Django templates

# Tests
uv run pytest                       # all tests
uv run pytest mapping_violence/     # single app
uv run pytest -k "test_name"        # single test

# Database
make mm                             # makemigrations
make migrate                        # migrate
make fixtures                       # load weapon_types.json seed data

# CSS (required when changing templates)
make tailwind                       # starts Tailwind watcher (npm-based, from theme/static_src/)
```

Pre-commit hooks run ruff, ruff-format, isort, and djhtml automatically. When hooks reformat files on the first attempt, re-`git add` the modified files and commit again.

## Architecture

**Mapping Violence** is a Django 5.1+ research application for documenting patterns of early modern violence (Venice and surrounding regions, 16th–17th centuries). It combines a structured crime database with a CMS for project content.

### Apps

| App | Purpose |
|-----|---------|
| `mapping_violence` | Core domain — Crime records, Person, Weapon, Event, Witness models; views for crime list/detail and home page |
| `locations` | Geographic hierarchy — City → Location with coordinate fallback; GeoJSON API for the map |
| `historical_dates` | EDTF-based uncertain date handling; provides `HistoricalDateField` used in Crime, Event, Witness |
| `content` | Wagtail CMS — `HomePageContent` snippet, `ProjectPerson` snippet (team/advisory board), `GeneralPage` StreamField pages |
| `config` | Django settings, root URL conf, allauth adapter (signup disabled; invite-only) |
| `theme` | Tailwind CSS source (static_src/) and compiled output |

### Key model relationships

```
Crime
  ├── victim        (M2M → Person)
  ├── perpetrator   (M2M → Person)
  ├── judge         (FK  → Person)
  ├── location      (FK  → Location → City)
  ├── weapon        (FK  → Weapon)
  ├── connected_event (FK → Event)
  └── historical_date (FK → HistoricalDate)   # uncertain dates via EDTF

Person ←→ Person  (M2M through PersonRelation → PersonRelationType)

Location
  ├── city (FK → City)
  └── effective_latitude/longitude  # property: falls back to City coords if blank
```

`Crime` tracks both a standard `DateField` and a `HistoricalDateField` for cases where dates are uncertain or approximate. The `HistoricalDate` model stores an EDTF string and computes `start_date`/`end_date`/`certainty` on save.

### URL structure

```
/                        → home page (HomePageContent + ProjectPerson snippets)
/map/                    → Leaflet map with collapsible filter panel
/api/locations.geojson   → GeoJSON endpoint (filtered by city, crime_type, year, weapon_category)
/data/                   → paginated crime table (CrimeFilter + CrimeTable)
/crime/<id>/             → crime detail page
/admin/                  → Django Unfold admin
/cms/                    → Wagtail admin
/<path>/                 → Wagtail catch-all pages
```

### Admin

Uses **django-unfold** (not stock Django admin). `CrimeAdmin` extends `ImportExportModelAdmin` for CSV import/export via custom resource widgets (`PersonWidget`, `WeaponWidget`, etc. in `mapping_violence/resources.py`) that do `get_or_create` lookups by name. The `input_by` / `updated_by` fields on `Crime` are auto-populated from `request.user` in `save_model`.

### Map frontend

`/map/` uses Leaflet with Alpine.js for the sliding drawer. Filter state (city, crime type, weapon category, year range, color-by mode) is persisted to URL query params via `history.replaceState`. The GeoJSON endpoint returns per-crime data including `fatality`, `victim_gender`, and `perpetrator_gender` for client-side color-by rendering.

### Data loading

Bulk data comes in via CSV import through the Django admin (CrimeAdmin import). Seed fixtures: `make fixtures` loads `fixtures/weapon_types.json`. Source CSVs live in `static-data/`.

### Settings and environment

Settings live in `config/settings.py` and read from a `.env` file. Required env vars: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`, `SECRET_KEY`. Optional: `OBJ_STORAGE` (S3-compatible media), social auth keys for ORCID/GitHub/Slack.
