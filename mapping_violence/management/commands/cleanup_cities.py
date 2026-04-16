"""
Clean up city records where location-level data was imported as city names.

Usage:
    uv run manage.py cleanup_cities                  # dry-run: show what would change
    uv run manage.py cleanup_cities --apply          # apply changes
    uv run manage.py cleanup_cities --whitespace     # only fix whitespace dupes
    uv run manage.py cleanup_cities --report         # full CSV report of all cities

The main issue: during CSV import, records like "Bologna piazza san martino"
were created as City records instead of being split into City="Bologna" +
Location="piazza san martino". Each fake city has one Location child with the
same name, and crimes link through that Location.

This command:
1. Identifies fake cities that start with a known base city name
2. Re-points their Location children to the real base city
3. Cleans up the Location name to just the location detail
4. Deletes the orphaned fake city records
5. Merges exact duplicates caused by trailing whitespace
"""

import csv
import sys

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from locations.models import City, Location


def find_base_city(fake_name, base_cities):
    """Find the best matching base city for a fake city name.

    Returns (base_city, location_detail) or (None, None).
    """
    name = fake_name.strip()

    for base in sorted(base_cities, key=lambda c: -len(c.name.strip())):
        base_name = base.name.strip().rstrip(",")
        if not name.lower().startswith(base_name.lower()):
            continue

        remainder = name[len(base_name) :]

        # Exact match (possibly with whitespace) — this is a whitespace dupe
        if not remainder.strip():
            return base, ""

        # Must start with a separator to count as "CityName + detail"
        if remainder[0] in (",", ";", " "):
            detail = remainder.lstrip(",; ").strip()
            if detail:
                return base, detail
            else:
                return base, ""  # whitespace dupe

    return None, None


class Command(BaseCommand):
    help = "Clean up city records that contain location-level data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually apply changes (default is dry-run)",
        )
        parser.add_argument(
            "--whitespace",
            action="store_true",
            help="Only fix whitespace duplicates, skip location-in-name fixes",
        )
        parser.add_argument(
            "--report",
            action="store_true",
            help="Output a CSV report of all cities and their status",
        )

    def handle(self, *args, **options):
        if options["report"]:
            return self.report()

        apply = options["apply"]
        whitespace_only = options["whitespace"]

        # Base cities: those with coordinates
        base_cities = list(City.objects.exclude(latitude__isnull=True))
        # Also include cities without coords that have a clean short name
        # (not containing location detail)

        fake_cities = City.objects.filter(latitude__isnull=True).order_by("name")

        whitespace_dupes = []  # (fake_city, base_city)
        location_in_name = []  # (fake_city, base_city, location_detail)
        unmatched = []

        for fc in fake_cities:
            base, detail = find_base_city(fc.name, base_cities)
            if base is None:
                unmatched.append(fc)
            elif detail == "":
                whitespace_dupes.append((fc, base))
            else:
                location_in_name.append((fc, base, detail))

        # ── Report ───────────────────────────────────────────────────────
        self.stdout.write(
            self.style.NOTICE(
                f"\nFound {len(whitespace_dupes)} whitespace duplicates, "
                f"{len(location_in_name)} location-in-name cities, "
                f"{len(unmatched)} unmatched cities"
            )
        )

        if whitespace_dupes:
            self.stdout.write(self.style.WARNING("\n── Whitespace duplicates ──"))
            for fc, base in whitespace_dupes[:10]:
                loc_count = Location.objects.filter(city=fc).count()
                self.stdout.write(
                    f"  {repr(fc.name)} (ID={fc.id}) → merge into "
                    f"{repr(base.name)} (ID={base.id}), {loc_count} locations"
                )
            if len(whitespace_dupes) > 10:
                self.stdout.write(f"  ... and {len(whitespace_dupes) - 10} more")

        if location_in_name and not whitespace_only:
            self.stdout.write(
                self.style.WARNING("\n── Location-in-name cities (sample) ──")
            )
            for fc, base, detail in location_in_name[:15]:
                self.stdout.write(
                    f"  {repr(fc.name)} (ID={fc.id})\n"
                    f"    → City: {repr(base.name)}, Location: {repr(detail)}"
                )
            if len(location_in_name) > 15:
                self.stdout.write(f"  ... and {len(location_in_name) - 15} more")

        if not apply:
            self.stdout.write(
                self.style.NOTICE(
                    "\nDry run — no changes made. Use --apply to execute."
                )
            )
            return

        # ── Apply changes ────────────────────────────────────────────────
        merged_count = 0
        relocated_count = 0

        with transaction.atomic():
            # 1. Fix whitespace duplicates
            for fc, base in whitespace_dupes:
                locs = Location.objects.filter(city=fc)
                for loc in locs:
                    # Check if a matching location already exists under base
                    existing = Location.objects.filter(
                        city=base, name=loc.name.strip() or base.name.strip()
                    ).first()
                    if existing:
                        # Move crimes from this location to the existing one
                        from mapping_violence.models import Crime

                        Crime.objects.filter(address=loc).update(address=existing)
                        loc.delete()
                    else:
                        loc.name = loc.name.strip() or base.name.strip()
                        loc.city = base
                        loc.save()
                fc.delete()
                merged_count += 1

            # 2. Fix location-in-name cities
            if not whitespace_only:
                for fc, base, detail in location_in_name:
                    locs = Location.objects.filter(city=fc)
                    for loc in locs:
                        loc_name = detail if detail else loc.name.strip()
                        # Avoid unique constraint collision
                        existing = Location.objects.filter(
                            city=base,
                            category_of_space=loc.category_of_space,
                            description_of_location=loc.description_of_location,
                        ).first()
                        if (
                            existing
                            and existing.name == loc_name
                            and existing.id != loc.id
                        ):
                            # Merge into existing
                            from mapping_violence.models import Crime

                            Crime.objects.filter(address=loc).update(address=existing)
                            loc.delete()
                        else:
                            loc.name = loc_name
                            loc.city = base
                            try:
                                loc.save()
                            except Exception:
                                # Unique constraint — merge instead
                                from mapping_violence.models import Crime

                                target = (
                                    Location.objects.filter(
                                        city=base,
                                        category_of_space=loc.category_of_space,
                                        description_of_location=loc.description_of_location,
                                    )
                                    .exclude(id=loc.id)
                                    .first()
                                )
                                if target:
                                    Crime.objects.filter(address=loc).update(
                                        address=target
                                    )
                                    loc.delete()
                    fc.delete()
                    relocated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Merged {merged_count} whitespace duplicates, "
                f"relocated {relocated_count} location-in-name cities."
            )
        )

        # Show remaining orphaned cities
        orphans = City.objects.annotate(loc_count=Count("location")).filter(loc_count=0)
        if orphans.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"\n{orphans.count()} cities now have zero locations "
                    f"(may be safe to review/delete)."
                )
            )

    def report(self):
        """Output a CSV of all cities with their status."""
        base_cities = list(City.objects.exclude(latitude__isnull=True))
        writer = csv.writer(sys.stdout)
        writer.writerow(
            [
                "id",
                "name",
                "has_coords",
                "status",
                "base_city",
                "location_detail",
                "location_count",
                "crime_count",
            ]
        )

        for city in City.objects.all().order_by("name"):
            has_coords = bool(city.latitude)
            loc_count = Location.objects.filter(city=city).count()
            from mapping_violence.models import Crime

            crime_count = Crime.objects.filter(address__city=city).count()

            if has_coords:
                status = "base"
                base_name = ""
                detail = ""
            else:
                base, detail = find_base_city(city.name, base_cities)
                if base:
                    status = "whitespace_dupe" if detail == "" else "location_in_name"
                    base_name = base.name
                else:
                    status = "unmatched"
                    base_name = ""
                    detail = ""

            writer.writerow(
                [
                    city.id,
                    city.name,
                    has_coords,
                    status,
                    base_name,
                    detail,
                    loc_count,
                    crime_count,
                ]
            )
