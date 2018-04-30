import logging
import requests
import os
import base64
import json
import arrow

from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.conf import settings
from datauploader.tasks import fetch_fitbit_data
from urllib.parse import parse_qs
from open_humans.models import OpenHumansMember
from .models import FitbitMember


# Set up logging.
logger = logging.getLogger(__name__)

# Fitbit settings
fitbit_authorize_url = 'https://www.fitbit.com/oauth2/authorize'
fitbit_token_url = 'https://api.fitbit.com/oauth2/token'


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
    print(encode_fitbit_auth)
    b64header = base64.b64encode(encode_fitbit_auth.encode("UTF-8")).decode("UTF-8")
    # Add the payload of code and grant_type. Construct headers
    payload = {'code': code, 'grant_type': 'authorization_code'}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': 'Basic %s' % (b64header)}
    # Make request for access token
    r = requests.post(fitbit_token_url, payload, headers=headers)
    # print(r.json())

    rjson = r.json()

    oh_id = request.user.oh_member.oh_id
    oh_user = OpenHumansMember.objects.get(oh_id=oh_id)

    # Save the user as a FitbitMember and store tokens
    try:
        fitbit_member = FitbitMember.objects.get(userid=rjson['user_id'])
        fitbit_member.access_token = rjson['access_token']
        fitbit_member.refresh_token = rjson['refresh_token']
        fitbit_member.expires_in = rjson['expires_in']
        fitbit_member.scope = rjson['scope']
        fitbit_member.token_type = rjson['token_type']
        fitbit_member.save()
    except FitbitMember.DoesNotExist:
        fitbit_member = FitbitMember.objects.get_or_create(
            user=oh_user,
            userid=rjson['user_id'],
            access_token=rjson['access_token'],
            refresh_token=rjson['refresh_token'],
            expires_in=rjson['expires_in'],
            scope=rjson['scope'],
            token_type=rjson['token_type'])

    # Fetch user's existing data from OH
    # We are going to use the pip package open-humans-api for this  
    # fitbit_data = get_existing_fitbit(oh_user.access_token)
    # print(fitbit_data)


    # Fetch user's data from Fitbit (update the data if it already existed)
    alldata = fetch_fitbit_data.delay(fitbit_member.id, rjson['access_token'])

    # replace_fitbit(fitbit_member.user, fitbit_data)

    # metadata = {
    #     'tags': ['fitbit', 'tracker', 'activity'],
    #     'description': 'File with Fitbit data',
    # }

    # xfer_to_open_humans.delay(alldata, metadata, oh_id=oh_id)

    context = {'oh_proj_page': settings.OH_ACTIVITY_PAGE}
    return render(request, 'main/complete.html',
                  context=context)


def complete(request):
    """
    Receive user from Open Humans. Store data, start upload.
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

        auth_url = 'https://www.fitbit.com/oauth2/authorize?response_type=code&client_id='+settings.FITBIT_CLIENT_ID+'&scope=activity%20nutrition%20heartrate%20location%20nutrition%20profile%20settings%20sleep%20social%20weight'

        context = {'oh_id': oh_member.oh_id,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE,
                   'authorization_url': auth_url}
        return render(request, 'main/fitbit.html',
                      context=context)

    logger.debug('Invalid code exchange. User returned to starting page.')
    return redirect('/')


def oh_code_to_member(code):
    """
    Exchange code for token, use this to create and return OpenHumansMember.
    If a matching OpenHumansMember exists, update and return it.
    """
    if settings.OPENHUMANS_CLIENT_SECRET and \
       settings.OPENHUMANS_CLIENT_ID and code:
        print('{}/complete/oh'.format(settings.OPENHUMANS_APP_BASE_URL))
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri':
            '{}/complete/oh'.format(settings.OPENHUMANS_APP_BASE_URL),
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
