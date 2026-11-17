FROM python:slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/venv

# Set working directory
WORKDIR /app

# Copy project
COPY . /app/

RUN uv lock

# collect front end assets
RUN uv run manage.py collectstatic --no-input

CMD uv run manage.py runserver 0.0.0.0:8000
