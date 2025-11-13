# Setting up Mapping Violence

## Quickstart

This quickstart requires a working Docker Desktop installation and git:

- Clone the repository:

  ```sh
  git clone https://github.com/chnm/mapping_violence.git
  cd mapping_violence
  ```

- Set up and run the Docker containers:

  ```sh
  docker-compose up
  ```

This will build the Django application and PostgreSQL database containers. The first run may take some time as it downloads dependencies and builds the containers.

The website will be available at <http://localhost:8000>.

## Detailed installation

The [quickstart above](#quickstart) should get you started. Each step has some additional detail below.

### Clone the repository

Using the console, navigate to the root directory in which your projects live and clone this project's repository:

```sh
git clone https://github.com/chnm/mapping_violence.git
cd mapping_violence
```

### Set up the environment (optional)

The Mapping Violence Django site can use environment variables defined in a `.env` file. The Docker setup includes default environment variables, but you can customize them by creating a `.env` file:

```sh
cp .env .env.local
```

Then edit `.env.local` to customize any settings as needed.

### Set up a local Python environment (optional)

For development outside of Docker, you can set up a local Python environment using Poetry.

This project requires Python 3.12+ and [uv](https://docs.astral.sh/uv/) for dependency management.

Install uv if you haven't already:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install the project dependencies:

```sh
uv sync
```

### Configure VSCode formatters (optional)

For developers who use [Visual Studio Code](https://code.visualstudio.com/), you may wish to install certain [extensions](https://marketplace.visualstudio.com/VSCode) to support easier code formatting.

This repository includes a `.vscode/settings.json` file that sets the [Prettier extension](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode) as the default code formatter. It also sets the [Black extension](https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter) as the formatter for Python files.

### Install pre-commit

We use `pre-commit` to automatically run our linting tools before a commit takes place. To install `pre-commit`, run the following commands from within the `mapping_violence` directory:

```sh
uv install  # if not already done
uv run pre-commit install
```

Before each commit, `pre-commit` will execute and run our linting checks. If any task fails, it will attempt to resolve the issue automatically and ask you to re-stage the changed files.

### Build the frontend

The frontend uses Tailwind CSS and is managed through Django's tailwind integration. Node.js 22.17.0 is required.

We recommend using [nvm](https://github.com/nvm-sh/nvm) for Node.js version management:

```sh
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | sh
nvm install 22.17.0
nvm use 22.17.0
```

Install frontend dependencies:

```sh
npm install
```

To start the Tailwind CSS compiler in development mode:

```sh
make tailwind
```

Or using Poetry directly:

```sh
uv run manage.py tailwind start
```

### Set up and run the Docker containers

Mapping Violence depends on a PostgreSQL database. You can use [`docker-compose`](https://docs.docker.com/compose/) to run the database alongside the Django application.

To build and run the Docker containers:

```sh
docker-compose up
```

This will:
- Build the Django application container
- Start a PostgreSQL 17 database container
- Run database migrations
- Start the Django development server on port 8000

### Development commands

The project includes a Makefile with common development commands:

```sh
# Run the development server locally (without Docker)
make preview

# Make database migrations
make mm

# Apply database migrations
make migrate

# Start Tailwind CSS compiler
make tailwind

# Load initial data fixtures
make fixtures
```

## Alternative setups

### Running locally without Docker

After setting up the local Python environment with Poetry, you can run the application locally against a PostgreSQL database.

#### PostgreSQL setup

You can install PostgreSQL from Homebrew if you're on macOS:

```sh
brew install postgresql
brew services start postgresql
```

Create the database and user:

```sh
createdb mapping_violence
createuser -s mapping_violence
```

#### Running the application

With PostgreSQL running, you can start the Django development server:

```sh
uv run manage.py migrate
uv run manage.py runserver
```

Or using the Makefile:

```sh
make migrate
make preview
```

### Environment variables

The application uses the following key environment variables:

- `DEBUG`: Set to `True` for development
- `DJANGO_SECRET_KEY`: Secret key for Django (auto-generated if not set)
- `DB_HOST`: Database host (default: localhost)
- `DB_PORT`: Database port (default: 5432)
- `DB_NAME`: Database name (default: mapping_violence)
- `DB_USER`: Database user (default: mapping_violence)
- `DB_PASSWORD`: Database password

See the `docker-compose.yml` file for the complete list of environment variables.

## Additional setup

### Django Admin

To create a superuser for the Django admin interface:

```sh
# Using Docker
docker-compose exec app uv run manage.py createsuperuser

# Or locally
uv run manage.py createsuperuser
```

The Django admin will be available at <http://localhost:8000/admin/>.

### Loading initial data

The project includes fixtures for initial data such as weapon types. After running migrations, you can load these fixtures:

```sh
# Using Docker
docker-compose exec app uv run manage.py loaddata fixtures/weapon_types.json

# Or locally
uv run manage.py loaddata fixtures/weapon_types.json

# Or using the Makefile
make fixtures
```

This will populate the database with basic weapon categories (Firearm, Edged Weapon, Bludgeon) and weapons (Rifle, Sword, Club).

#### Creating fixtures from CSV

The project includes a CSV template and conversion script for easily creating weapon fixtures:

1. **Edit the CSV template**: `fixtures/weapon_types.csv`
   - Contains columns: `category_name`, `weapon_name`, `weapon_definition`
   - Add or modify rows as needed

2. **Convert CSV to fixture JSON**:
   ```sh
   python util/csv_to_fixture.py fixtures/weapon_types.csv
   ```

3. **Load the generated fixture**:
   ```sh
   make fixtures
   ```

The script automatically creates weapon categories and assigns weapons to them based on the CSV data.

### Running tests

To run the test suite:

```sh
# Using Docker
docker-compose exec app uv run manage.py test

# Or locally
uv run manage.py test
```

### Code formatting

The project uses Black for Python code formatting and djhtml for Django template formatting:

```sh
uv run black .
uv run djhtml templates/
```

These tools will run automatically via pre-commit hooks when you commit changes.
