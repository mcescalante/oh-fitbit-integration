release: python manage.py migrate
web: gunicorn oh_fitbit.wsgi --log-file -
worker: celery -A oh_fitbit worker --without-gossip --without-mingle --without-heartbeat
