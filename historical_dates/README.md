# Historical Dates for Django

A reusable Django app to handle uncertain, partial, approximate, and ranged historical dates with native [EDTF](https://www.loc.gov/standards/datetime/) (Extended Date/Time Format) support.

## Features
- Supports human-readable display dates
- Parses EDTF strings into sortable start and end dates
- Validates EDTF syntax on admin and forms
- Provides a `HistoricalDateField` for referencing in other models
- Django admin integration

## Install

`poetry add django edtf`

Add `historical_dates` to `INSTALLED_APPS`.

## Usage

```python
from historical_dates.fields import HistoricalDateField

class Artifact(models.Model):
    production_date = HistoricalDateField()

