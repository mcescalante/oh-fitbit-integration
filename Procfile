release: python manage.py migrate
web: gunicorn fitbit.wsgi --log-file=-
worker: celery worker -A datauploader
