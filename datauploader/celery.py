"""
Celery set up, as recommended by celery
http://celery.readthedocs.org/en/latest/django/first-steps-with-django.html

Celery will automatically discover and use methods within INSTALLED_APPs that
have the @shared_task decorator.
"""
# absolute_import prevents conflicts between project celery.py file
# and the celery package.
from __future__ import absolute_import

import os
import requests

from celery import Celery
from celery.schedules import crontab

from django.conf import settings

# from main.models import FitbitMember

CELERY_BROKER_URL = os.getenv('REDIS_URL')

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'fitbit.settings')

app = Celery('datauploader', broker=CELERY_BROKER_URL)
# Set up Celery with Heroku CloudAMQP (or AMQP in local dev).
app.conf.update({
    'BROKER_URL': CELERY_BROKER_URL,
    # Recommended settings. See: https://www.cloudamqp.com/docs/celery.html
    'BROKER_POOL_LIMIT': 1,
    'BROKER_HEARTBEAT': None,
    'BROKER_CONNECTION_TIMEOUT': 30,
    'CELERY_RESULT_BACKEND': CELERY_BROKER_URL,
    'CELERY_SEND_EVENTS': False,
    'CELERY_EVENT_QUEUE_EXPIRES': 60,
})

# Set up Celery Beat (periodic/timed tasks)
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Calls test('hello') every 10 seconds.
    sender.add_periodic_task(10.0, test.s('hello'), name='add every 10')



# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

@app.task
def test(arg):
    '''
    Fetches all of the fitbit data for a given user
    '''
    fitbit_urls = [
        # Requires the 'settings' scope, which we haven't asked for
        # {'name': 'devices', 'url': '/-/devices.json', 'period': None},

        {'name': 'activities-overview',
         'url': '/{user_id}/activities.json',
         'period': None},

        # interday timeline data
        {'name': 'heart',
         'url': '/{user_id}/activities/heart/date/{start_date}/{end_date}.json',
         'period': 'month'},
        # MPB 2016-12-12: Although docs allowed for 'year' for this endpoint,
        # switched to 'month' bc/ req for full year started resulting in 504.
        {'name': 'tracker-activity-calories',
         'url': '/{user_id}/activities/tracker/activityCalories/date/{start_date}/{end_date}.json',
         'period': 'month'},
        {'name': 'tracker-calories',
         'url': '/{user_id}/activities/tracker/calories/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'tracker-distance',
         'url': '/{user_id}/activities/tracker/distance/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'tracker-elevation',
         'url': '/{user_id}/activities/tracker/elevation/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'tracker-floors',
         'url': '/{user_id}/activities/tracker/floors/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'tracker-minutes-fairly-active',
         'url': '/{user_id}/activities/tracker/minutesFairlyActive/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'tracker-minutes-lightly-active',
         'url': '/{user_id}/activities/tracker/minutesLightlyActive/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'tracker-minutes-sedentary',
         'url': '/{user_id}/activities/tracker/minutesSedentary/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'tracker-minutes-very-active',
         'url': '/{user_id}/activities/tracker/minutesVeryActive/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'tracker-steps',
         'url': '/{user_id}/activities/tracker/steps/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'weight-log',
         'url': '/{user_id}/body/log/weight/date/{start_date}/{end_date}.json',
         'period': 'month'},
        {'name': 'weight',
         'url': '/{user_id}/body/weight/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'sleep-awakenings',
         'url': '/{user_id}/sleep/awakeningsCount/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'sleep-efficiency',
         'url': '/{user_id}/sleep/efficiency/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'sleep-minutes-after-wakeup',
         'url': '/{user_id}/sleep/minutesAfterWakeup/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'sleep-minutes',
         'url': '/{user_id}/sleep/minutesAsleep/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'awake-minutes',
         'url': '/{user_id}/sleep/minutesAwake/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'minutes-to-sleep',
         'url': '/{user_id}/sleep/minutesToFallAsleep/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'sleep-start-time',
         'url': '/{user_id}/sleep/startTime/date/{start_date}/{end_date}.json',
         'period': 'year'},
        {'name': 'time-in-bed',
         'url': '/{user_id}/sleep/timeInBed/date/{start_date}/{end_date}.json',
         'period': 'year'},
    ]
    intraday_urls = [
        # intraday timeline data
        # {'name': 'intraday-heart',
        #  'url': '/-/activities/heart/date/{date}/1d/1sec.json',
        #  'period': 'day'},
        # {'name': 'intraday-steps',
        #  'url': '/-/activities/steps/date/{date}/1d/1min.json',
        #  'period': 'day'},
    ]
    from open_humans.models import OpenHumansMember
    for user in OpenHumansMember.objects.all():
        print(user)

        # Get initial information about user from Fitbit
        print("attempting query ")
        headers = {'Authorization': "Bearer %s" % user.fitbit_member.access_token}
        # query_result = requests.get('https://api.fitbit.com/1/user/-/profile.json', headers=headers)
        print(requests.get('https://api.fitbit.com/1/user/-/profile.json', headers=headers))
        # # Refresh token if the result is 401
        # # TODO: update this so it just checks the expired field.
        # if query_result.status_code == 401:
        #     print("old token", fitbit_member.access_token)
        #     fitbit_member.refresh_tokens()
        #     print("new token", fitbit_member.access_token)

        # # Store the user ID since it's used in all future queries
        # user_id = query_result.json()['user']['encodedId']
        # member_since = query_result.json()['user']['memberSince']
        # start_date = arrow.get(member_since, 'YYYY-MM-DD').format('YYYY-MM-DD')

        # # Loop over URLs, format with user info.
        # results = {}
        # for url in fitbit_urls:
        #     fitbit_api_base_url = 'https://api.fitbit.com/1/user'
        #     final_url = fitbit_api_base_url + url['url'].format(user_id=user_id,
        #                                                         start_date=start_date,
        #                                                         end_date=arrow.utcnow().format('YYYY-MM-DD'))
        #     print("Fetching data from: ", final_url)
        #     # Fetch the data
        #     r = rr.get(url=final_url, headers=headers, realms=["Fitbit"])
        #     # Append the results to results dictionary with url "name" as the key
        #     results[url['name']] = r.json()

    print('task ran')
