# Mapping Violence

A Django web application for documenting and analyzing patterns of early modern violence. This project powers the [Mapping Early Modern Violence](https://earlymodernviolence.org/) website, providing historians with tools to explore historical crime data from Venice and surrounding regions.

## About the Project

Mapping Violence is a collaborative research project that examines violent crime in early modern Europe, focusing on cases from Venice and the Venetian terraferma. The project digitizes and analyzes court records, witness testimonies, and archival documents to understand patterns of violence, social relationships, and legal proceedings in the 16th and 17th centuries.

**⚠️ Work in Progress**: This project is actively under development. Features and data presented here are preliminary unless they appear on the production website at [earlymodernviolence.org](https://earlymodernviolence.org/).

## Features

- **Crime Database**: Comprehensive cataloging of violent crimes with detailed metadata
- **Person Registry**: Network of individuals involved in criminal cases (victims, perpetrators, witnesses, judges)
- **Historical Date Handling**: Specialized fields for managing uncertain and approximate historical dates
- **Geographic Data**: Hierarchical location system with cities and specific locations, supporting historical place names and modern coordinates
- **Content Management**: Wagtail CMS integration for managing static content and project information
- **Data Import/Export**: CSV-based data ingestion and export capabilities
- **Advanced Search**: Multi-faceted search and filtering across crimes, people, and locations

## Technology Stack

- **Backend**: Django 5.1+ with Python 3.12
- **CMS**: Wagtail 7.1 for content administration
- **Database**: PostgreSQL 16 with PostGIS support
- **Frontend**: Tailwind CSS with Django templates
- **Authentication**: Django Allauth with social login support
- **Development**: Poetry for dependency management, Black for code formatting

## Key Models

- **Crime**: Central model storing details about violent incidents, court proceedings, and outcomes
- **Person**: Individuals involved in cases (victims, perpetrators, witnesses, court officials)
- **Event**: Ceremonial or social events connected to crimes (feast days, weddings, etc.)
- **Weapon**: Categorized inventory of weapons used in violent acts
- **City**: Towns and cities with general coordinates and administrative information
- **Location**: Specific places within cities, including category of space and detailed descriptions

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Node.js (for frontend dependencies)
- Poetry (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone git@github.com:chnm/mv-django.git
cd mapping_violence
```

2. Install Python dependencies:
```bash
poetry install
```

3. Install frontend dependencies:
```bash
npm install
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials and other settings
```

5. Set up the database:
```bash
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
```

6. Load initial data (optional):
```bash
poetry run python manage.py loaddata fixtures/weapon_types.json
```

7. Run the development server:
```bash
poetry run python manage.py runserver
```

## Development

### Code Style

This project uses Black for Python code formatting and follows Django best practices:

```bash
# Format code
poetry run black .

# Run linting
poetry run pylint mapping_violence/

# Format HTML templates
poetry run djhtml templates/
```

### Frontend Development

Frontend assets are managed with Tailwind CSS:

```bash
# Start Tailwind development server
cd theme/static_src
npm run dev

# Build for production
npm run build
```

### Testing

```bash
# Run tests
poetry run pytest
```

## Project Structure

```
mapping_violence/
├── config/              # Django settings and configuration
├── mapping_violence/    # Main app with Crime, Person models
├── content/            # Wagtail CMS pages and content
├── locations/          # Geographic models and utilities
├── historical_dates/   # Custom date handling for uncertain dates
├── theme/             # Frontend theme and Tailwind configuration
├── templates/         # Django templates
├── static/           # Static assets
├── fixtures/         # Initial data fixtures
└── docs/            # Project documentation
```

## Data Model Overview

The application centers around documenting violent crimes with rich contextual information:

- **Crimes** are linked to **People** (victims, perpetrators, witnesses)
- **Historical dates** handle uncertainty in early modern records
- **Cities** and **Locations** provide hierarchical geographic context, allowing multiple location types within the same city
- **Events** connect crimes to social and religious occasions
- **Weapons** are categorized and defined for analysis

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Make your changes following the code style guidelines
4. Run tests and ensure they pass
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feat/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

This project is developed by the [Roy Rosenzweig Center for History and New Media](https://rrchnm.org/) at George Mason University.

## Contact

- Project Lead: Amanda Madden
- Lead Developer: Jason Heppler (jheppler@gmu.edu)

For technical issues, please use the GitHub issue tracker.
