# Introduction to Mapping Early Modern Violence

This is the documentation for the Mapping Early Modern Violence project that powers the [https://earlymodernviolence.org/](https://earlymodernviolence.org/) website.

## Disclaimer

**This project is a work in progress.** Nothing presented in this repo--whether in the source code or issue tracker--is a final product unless it is marked as such or appears on [https://earlymodernviolence.org/](https://earlymodernviolence.org/). In-progress updates may appear on [https://dev.earlymodernviolence.org/](https://dev.earlymodernviolence.org/).

## Technology stack

The standard technology stack for development of Mapping Early Modern Violence within RRCHNM consists of the following base:

- macOS
- [Homebrew](https://brew.sh) - package manager for installing system software on OSX
- [Python 3.12](https://docs.python.org/3.12/) and [Poetry](https://python-poetry.org/docs/)
- [Jinja2 templates](https://jinja.palletsprojects.com/) for front-end rendering.
- [Wagtail CMS](https://wagtail.io) for content administration.
- [PostgreSQL 16](https://www.postgresql.org/) is the database we use in production and locally.
- [Psycopg](https://www.psycopg.org/) is the Python library that lets Python talk to Postges.
- Additional dependencies, listed below.

## Additional dependencies

- [Node](https://nodejs.org) - Used for downloading and managing front-end dependencies and assets. Front-end dependencies are listed in the project's `package.json` file.
- [pyenv](https://github.com/pyenv/pyenv)
- [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv)

## Versions

Versions for most front-end packages are kept updated in the project's `package.json` file.

Versions for back-end software including Django, Wagtail, Jinja, etc. are kept in the project's `pyproject.json` file.
