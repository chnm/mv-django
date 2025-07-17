preview :
	poetry run python manage.py runserver

mm :
	poetry run python manage.py makemigrations

migrate :
	poetry run python manage.py migrate

tailwind :
	poetry run python manage.py tailwind start

fixtures :
	poetry run python manage.py loaddata fixtures/weapon_types.json
