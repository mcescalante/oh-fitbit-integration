import logging
import requests
import os
import base64
import json
import arrow

from requests_respectful import RespectfulRequester
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.conf import settings
from datauploader.tasks import xfer_to_open_humans
from urllib.parse import parse_qs
from open_humans.models import OpenHumansMember
from .models import FitbitMember


# Set up logging.
logger = logging.getLogger(__name__)

# OAuth1 for Nokia Health
# Credentials obtained during the registration.
client_key = settings.NOKIA_CONSUMER_KEY
client_secret = settings.NOKIA_CONSUMER_SECRET
callback_uri = settings.NOKIA_CALLBACK_URL
oh_proj_page = settings.OH_ACTIVITY_PAGE

# Fitbit settings
fitbit_authorize_url = 'https://www.fitbit.com/oauth2/authorize'
fitbit_token_url = 'https://api.fitbit.com/oauth2/token'

if settings.REMOTE is True:
    from urllib.parse import urlparse
    url_object = urlparse(os.getenv('REDIS_URL'))
    logger.info('Connecting to redis at %s:%s',
        url_object.hostname,
        url_object.port)
    RespectfulRequester.configure(
        redis={
            "host": url_object.hostname,
            "port": url_object.port,
            "password": url_object.password,
            "database": 0
        },
        safety_threshold=5)

# Requests Respectful (rate limiting, waiting)
rr = RespectfulRequester()
rr.register_realm("Fitbit", max_requests=60, timespan=60)


def index(request):
    """
    Starting page for app.
    """

    context = {'client_id': settings.OPENHUMANS_CLIENT_ID,
               'oh_proj_page': settings.OH_ACTIVITY_PAGE}

    return render(request, 'main/index.html', context=context)


def complete_fitbit(request):

    code = request.GET['code']

    # Create Base64 encoded string of clientid:clientsecret for the headers for Fitbit
    # https://dev.fitbit.com/build/reference/web-api/oauth2/#access-token-request
    encode_fitbit_auth = str(settings.FITBIT_CLIENT_ID) + ":" + str(settings.FITBIT_CLIENT_SECRET)
    b64header = base64.b64encode(encode_fitbit_auth)
    # Add the payload of code and grant_type. Construct headers
    payload = {'code': code, 'grant_type': 'authorization_code'}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': 'Basic %s' % b64header}
    # Make request for access token
    r = requests.post(fitbit_token_url, payload, headers=headers)
    print(r.json())

    rjson = r.json() 

    oh_id = request.user.oh_member.oh_id
    oh_user = OpenHumansMember.objects.get(oh_id=oh_id)

    # Save the user as a FitbitMember and store tokens
    try:
        fitbit_member = FitbitMember.objects.get(userid=rjson['user_id'])
    except:
        fitbit_member = FitbitMember.objects.get_or_create(
            user=oh_user,
            userid=rjson['user_id'],
            access_token=rjson['access_token'],
            refresh_token=rjson['refresh_token'],
            expires_in=rjson['expires_in'],
            scope=rjson['scope'],
            token_type=rjson['token_type'])

    # Fetch user's data
    fetch_fitbit_data(fitbit_member, rjson['access_token'])
 
    context = {'oh_proj_page': settings.OH_ACTIVITY_PAGE}
    return render(request, 'main/complete.html',
                  context=context)


def fetch_fitbit_data(fitbit_member, access_token):
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

    # Get initial information about user from Fitbit
    headers = {'Authorization': "Bearer %s" % access_token}  
    query_result = requests.get('https://api.fitbit.com/1/user/-/profile.json', headers=headers)

    # Refresh token if the result is 401
    # TODO: update this so it just checks the expired field.
    if query_result.status_code == 401:
        print("old token", fitbit_member.access_token)
        fitbit_member.refresh_tokens()
        print("new token", fitbit_member.access_token)
    
    # Store the user ID since it's used in all future queries
    user_id = query_result.json()['user']['encodedId']
    member_since = query_result.json()['user']['memberSince']
    start_date = arrow.get(member_since, 'YYYY-MM-DD').format('YYYY-MM-DD')

    # Loop over URLs, format with user info.
    results = {}
    for url in fitbit_urls:
        fitbit_api_base_url = 'https://api.fitbit.com/1/user'
        final_url = fitbit_api_base_url + url['url'].format(user_id=user_id, 
                                                            start_date=start_date, 
                                                            end_date=arrow.utcnow().format('YYYY-MM-DD'))
        print("Fetching data from: ", final_url)
        # Fetch the data
        r = requests.get(final_url, headers=headers)
        # Append the results to results dictionary with url "name" as the key
        results[url['name']] = r.json()

    print(json.dumps(results)) # for debugging
    return json.dumps(results)


def complete(request):
    """
    Receive user from Open Humans and store.
    """
    logger.debug("Received user returning from Open Humans.")

    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    code = request.GET.get('code', '')
    oh_member = oh_code_to_member(code=code)

    if oh_member:
        # Log in the user.
        user = oh_member.user
        login(request, user,
              backend='django.contrib.auth.backends.ModelBackend')

        # Create an OAuth1 object, and obtain a request token
        oauth = OAuth1(client_key, client_secret=client_secret,
                       callback_uri=callback_uri)
        r = requests.post(url=request_token_url, auth=oauth)

        # Parse and save the resource owner key & secret (for use
        # in nokia_complete callback)
        credentials = parse_qs(r.text)
        request.session['resource_owner_key'] =\
            credentials.get('oauth_token')[0]
        request.session['resource_owner_secret'] =\
            credentials.get('oauth_token_secret')[0]

        # Generate the authorization URL
        authorize_url = authorization_url + '?oauth_token='
        authorize_url = authorize_url + request.session['resource_owner_key']

        # Render `complete.html`.
        context = {'oh_id': oh_member.oh_id,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE,
                   "redirect_url": authorize_url,
                   'nokia_consumer_key': settings.NOKIA_CONSUMER_KEY,
                   'nokia_callback_url': settings.NOKIA_CALLBACK_URL,
                   }
        return render(request, 'main/complete.html', context=context)

    logger.debug('Invalid code exchange. User returned to starting page.')
    return redirect('/')


def oh_code_to_member(code):
    """
    Exchange code for token, use this to create and return OpenHumansMember.
    If a matching OpenHumansMember exists, update and return it.
    """
    if settings.OPENHUMANS_CLIENT_SECRET and \
       settings.OPENHUMANS_CLIENT_ID and code:
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri':
            '{}/complete'.format(settings.OPENHUMANS_APP_BASE_URL),
            'code': code,
        }

        req = requests.post(
            '{}/oauth2/token/'.format(settings.OPENHUMANS_OH_BASE_URL),
            data=data,
            auth=requests.auth.HTTPBasicAuth(
                settings.OPENHUMANS_CLIENT_ID,
                settings.OPENHUMANS_CLIENT_SECRET
            )
        )
        data = req.json()

        if 'access_token' in data:
            oh_id = oh_get_member_data(
                data['access_token'])['project_member_id']
            try:
                oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
                logger.debug('Member {} re-authorized.'.format(oh_id))
                oh_member.access_token = data['access_token']
                oh_member.refresh_token = data['refresh_token']
                oh_member.token_expires = OpenHumansMember.get_expiration(
                    data['expires_in'])
            except OpenHumansMember.DoesNotExist:
                oh_member = OpenHumansMember.create(
                    oh_id=oh_id,
                    access_token=data['access_token'],
                    refresh_token=data['refresh_token'],
                    expires_in=data['expires_in'])
                logger.debug('Member {} created.'.format(oh_id))
            oh_member.save()

            return oh_member

        elif 'error' in req.json():
            logger.debug('Error in token exchange: {}'.format(req.json()))
        else:
            logger.warning('Neither token nor error info in OH response!')
    else:
        logger.error('OH_CLIENT_SECRET or code are unavailable')
    return None


def oh_get_member_data(token):
    """
    Exchange OAuth2 token for member data.
    """
    req = requests.get(
        '{}/api/direct-sharing/project/exchange-member/'
        .format(settings.OPENHUMANS_OH_BASE_URL),
        params={'access_token': token}
        )
    if req.status_code == 200:
        return req.json()
    raise Exception('Status code {}'.format(req.status_code))
    return None
