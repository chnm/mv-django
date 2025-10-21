# Default target - show help
.DEFAULT_GOAL := help

# Start the Django development server
preview:
	poetry run python manage.py runserver

# Check for any issues with the Django configuration
check:
	poetry run python manage.py check

# Open Django shell for interactive debugging
shell:
	poetry run python manage.py shell

# Database Management
# ==================

# Create new migration files based on model changes
mm:
	poetry run python manage.py makemigrations

# Apply migrations to the database
migrate:
	poetry run python manage.py migrate

# Show migration status
show-migrations:
	poetry run python manage.py showmigrations

# CSS
tailwind :
	poetry run python manage.py tailwind start

# Database Reset & Cleanup
# ========================

# WARNING: These commands will DESTROY all data in the database!
# Drop and recreate PostgreSQL database (for development only)
clean-db:
	@echo "WARNING: This will delete all database data!"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || exit 1
	poetry run python manage.py flush --noinput
	@echo "Database cleared. Run 'make setup-fresh-db' to recreate with migrations."

# Reset database and apply all migrations from scratch
reset-db: clean-db
	poetry run python manage.py migrate
	@echo "Fresh database created with all migrations applied."

# Data setup
# Create database backup (SQL dump)
backup-db:
	@echo "Creating database backup..."
	@mkdir -p backups
	@poetry run python -c "from django.conf import settings; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); import django; django.setup(); db = settings.DATABASES['default']; print(f\"pg_dump -h {db['HOST']} -p {db['PORT']} -U {db['USER']} -d {db['NAME']} > backups/backup_$$(date +%Y%m%d_%H%M%S).sql\")" | sh
	@echo "Database backup created in backups/ directory"

# Restore database from backup
restore-db:
	@echo "Available backups:"
	@ls -la backups/*.sql 2>/dev/null || echo "No backups found in backups/ directory"
	@echo ""
	@read -p "Enter backup filename (e.g., backup_20241201_143022.sql): " backup_file && \
	if [ ! -f "backups/$$backup_file" ]; then \
		echo "Error: Backup file backups/$$backup_file not found!"; \
		exit 1; \
	fi && \
	echo "WARNING: This will replace all current database data with backup data!" && \
	read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || exit 1 && \
	echo "Restoring database from backups/$$backup_file..." && \
	poetry run python -c "from django.conf import settings; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); import django; django.setup(); db = settings.DATABASES['default']; print(f\"psql -h {db['HOST']} -p {db['PORT']} -U {db['USER']} -d {db['NAME']} < backups/$$backup_file\")" | sh && \
	echo "Database restored successfully from backups/$$backup_file"

fixtures :
	poetry run python manage.py loaddata fixtures/weapon_types.json

# Utility Commands
# ================

# Create a superuser account
superuser:
	poetry run python manage.py createsuperuser

# Collect static files (for production)
collectstatic:
	poetry run python manage.py collectstatic --noinput

# Generate model relationship graph for core apps
models-graph:
	poetry run python manage.py graph_models mapping_violence locations historical_dates -g -o models_graph.png
	@echo "Model graph generated as models_graph.png"

# Show available commands
help:
	@echo "Available commands:"
	@echo "  preview         - Start Django development server"
	@echo "  check           - Check Django configuration"
	@echo "  shell           - Open Django shell"
	@echo ""
	@echo "Database Management:"
	@echo "  mm              - Create migration files"
	@echo "  migrate         - Apply migrations"
	@echo "  show-migrations - Show migration status"
	@echo "  clean-db        - Clear database (DESTRUCTIVE)"
	@echo "  reset-db        - Reset and recreate database"
	@echo "  backup-db       - Create database backup"
	@echo "  restore-db      - Restore from backup"
	@echo "  fixtures        - Load weapon types fixture data"
	@echo ""
	@echo "Utility Commands:"
	@echo "  superuser       - Create superuser account"
	@echo "  collectstatic   - Collect static files"
	@echo "  models-graph    - Generate model relationship diagram"
	@echo "  tailwind        - Start Tailwind CSS watcher"
