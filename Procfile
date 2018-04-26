release: python manage.py migrate
web: gunicorn fitbit.wsgi --log-file=-
worker: celery worker -A datauploader
beat: celery -A datauploader beat
