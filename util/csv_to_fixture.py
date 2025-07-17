#!/usr/bin/env python3
"""
Script to convert CSV data to Django fixture JSON format.
Usage: python scripts/csv_to_fixture.py fixtures/weapon_types.csv
"""

import csv
import json
import sys
from pathlib import Path


def csv_to_fixture(csv_file_path, output_file_path=None):
    """
    Convert CSV file to Django fixture JSON format.

    Args:
        csv_file_path: Path to the CSV file
        output_file_path: Optional path for output file. If None, uses same name with .json extension
    """
    csv_path = Path(csv_file_path)

    if not csv_path.exists():
        print(f"Error: CSV file {csv_file_path} not found")
        return False

    # Set output path
    if output_file_path is None:
        output_file_path = csv_path.with_suffix(".json")

    # Track categories and weapons
    categories = {}
    weapons = []
    category_pk = 1

    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                category_name = row["category_name"].strip()
                weapon_name = row["weapon_name"].strip()
                weapon_definition = row["weapon_definition"].strip()

                # Add category if not seen before
                if category_name not in categories:
                    categories[category_name] = category_pk
                    category_pk += 1

                # Add weapon
                weapons.append(
                    {
                        "name": weapon_name,
                        "definition": weapon_definition,
                        "category": categories[category_name],
                    }
                )

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return False

    # Build fixture data
    fixture_data = []

    # Add categories
    for category_name, pk in categories.items():
        fixture_data.append(
            {
                "model": "mapping_violence.weaponcategory",
                "pk": pk,
                "fields": {"name": category_name},
            }
        )

    # Add weapons
    for i, weapon in enumerate(weapons, 1):
        fixture_data.append(
            {
                "model": "mapping_violence.weapon",
                "pk": i,
                "fields": {
                    "name": weapon["name"],
                    "definition": weapon["definition"],
                    "category": weapon["category"],
                },
            }
        )

    # Write fixture file
    try:
        with open(output_file_path, "w", encoding="utf-8") as jsonfile:
            json.dump(fixture_data, jsonfile, indent=2, ensure_ascii=False)

        print(f"Successfully converted {csv_file_path} to {output_file_path}")
        print(f"Created {len(categories)} categories and {len(weapons)} weapons")
        return True

    except Exception as e:
        print(f"Error writing fixture file: {e}")
        return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/csv_to_fixture.py <csv_file>")
        print("Example: python scripts/csv_to_fixture.py fixtures/weapon_types.csv")
        sys.exit(1)

    csv_file = sys.argv[1]
    success = csv_to_fixture(csv_file)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
