release: python manage.py migrate
web: gunicorn oh-fitbit-integration.wsgi --log-file=-
worker: celery worker -A datauploader