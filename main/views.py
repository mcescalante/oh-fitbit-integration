import logging
import requests
import os
import base64
import json
import arrow

from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.conf import settings
from datauploader.tasks import fetch_googlefit_data
from urllib.parse import parse_qs
from open_humans.models import OpenHumansMember
from .models import GoogleFitMember
from .helpers import get_googlefit_file, check_update


# Set up logging.
logger = logging.getLogger(__name__)

# GoogleFit settings
googlefit_authorize_url = 'https://www.googlefit.com/oauth2/authorize'
googlefit_token_url = 'https://api.googlefit.com/oauth2/token'


def index(request):
    """
    Starting page for app.
    """
    if request.user.is_authenticated:
        return redirect('/dashboard')

    context = {'client_id': settings.OPENHUMANS_CLIENT_ID,
               'oh_proj_page': settings.OH_ACTIVITY_PAGE}

    return render(request, 'main/index.html', context=context)


def dashboard(request):
    if request.user.is_authenticated:
        if hasattr(request.user.oh_member, 'googlefit_member'):
            googlefit_member = request.user.oh_member.googlefit_member
            download_file = get_googlefit_file(request.user.oh_member)
            if download_file == 'error':
                logout(request)
                return redirect("/")
            auth_url = ''
            allow_update = check_update(googlefit_member)
        else:
            allow_update = False
            googlefit_member = ''
            download_file = ''
            auth_url = 'https://www.googlefit.com/oauth2/authorize?response_type=code&client_id='+settings.FITBIT_CLIENT_ID+'&scope=activity%20nutrition%20heartrate%20location%20nutrition%20profile%20settings%20sleep%20social%20weight'
        
        context = {
            'oh_member': request.user.oh_member,
            'googlefit_member': googlefit_member,
            'download_file': download_file,
            'connect_url': auth_url,
            'allow_update': allow_update
        }
        return render(request, 'main/dashboard.html',
                      context=context)
    return redirect("/")


def complete_googlefit(request):

    code = request.GET['code']

    # Create Base64 encoded string of clientid:clientsecret for the headers for GoogleFit
    # https://dev.googlefit.com/build/reference/web-api/oauth2/#access-token-request
    encode_googlefit_auth = str(settings.FITBIT_CLIENT_ID) + ":" + str(settings.FITBIT_CLIENT_SECRET)
    print(encode_googlefit_auth)
    b64header = base64.b64encode(encode_googlefit_auth.encode("UTF-8")).decode("UTF-8")
    # Add the payload of code and grant_type. Construct headers
    payload = {'code': code, 'grant_type': 'authorization_code'}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': 'Basic %s' % (b64header)}
    # Make request for access token
    r = requests.post(googlefit_token_url, payload, headers=headers)
    # print(r.json())

    rjson = r.json()

    oh_id = request.user.oh_member.oh_id
    oh_user = OpenHumansMember.objects.get(oh_id=oh_id)

    # Save the user as a GoogleFitMember and store tokens
    try:
        googlefit_member = GoogleFitMember.objects.get(userid=rjson['user_id'])
        googlefit_member.access_token = rjson['access_token']
        googlefit_member.refresh_token = rjson['refresh_token']
        googlefit_member.expires_in = rjson['expires_in']
        googlefit_member.scope = rjson['scope']
        googlefit_member.token_type = rjson['token_type']
        googlefit_member.save()
    except GoogleFitMember.DoesNotExist:
        googlefit_member, created = GoogleFitMember.objects.get_or_create(
            user=oh_user,
            userid=rjson['user_id'],
            access_token=rjson['access_token'],
            refresh_token=rjson['refresh_token'],
            expires_in=rjson['expires_in'],
            scope=rjson['scope'],
            token_type=rjson['token_type'])

    # Fetch user's data from GoogleFit (update the data if it already existed)
    # print(googlefit_member)
    alldata = fetch_googlefit_data.delay(googlefit_member.id, rjson['access_token'])

    context = {'oh_proj_page': settings.OH_ACTIVITY_PAGE}

    if googlefit_member:
        messages.info(request, "Your GoogleFit account has been connected, and your data has been queued to be fetched from GoogleFit")
        return redirect('/dashboard')

    logger.debug('Invalid code exchange. User returned to starting page.')
    messages.info(request, ("Something went wrong, please try connecting your "
                            "GoogleFit account again"))
    return redirect('/dashboard')


def remove_googlefit(request):
    if request.method == "POST" and request.user.is_authenticated:
        try:
            oh_member = request.user.oh_member
            api.delete_file(oh_member.access_token,
                            oh_member.oh_id,
                            file_basename="googlefit-data.json")
            messages.info(request, "Your GoogleFit account has been removed")
            googlefit_account = request.user.oh_member.googlefit_member
            googlefit_account.delete()
        except:
            googlefit_account = request.user.oh_member.googlefit_member
            googlefit_account.delete()
            messages.info(request, ("Something went wrong, please"
                          "re-authorize us on Open Humans"))
            logout(request)
            return redirect('/')
    return redirect('/dashboard')


def update_data(request):
    if request.method == "POST" and request.user.is_authenticated:
        print("entered update_data POST thing")
        oh_member = request.user.oh_member
        fetch_googlefit_data.delay(oh_member.googlefit_member.id, oh_member.googlefit_member.access_token)
        googlefit_member = oh_member.googlefit_member
        googlefit_member.last_submitted = arrow.now().format()
        googlefit_member.save()
        messages.info(request,
                      ("An update of your GoogleFit data has been started! "
                       "It can take some minutes before the first data is "
                       "available. Reload this page in a while to find your "
                       "data"))
        return redirect('/dashboard')


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

        context = {'oh_id': oh_member.oh_id,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE}

        if not hasattr(oh_member, 'googlefitmember'):
            auth_url = 'https://www.googlefit.com/oauth2/authorize?response_type=code&client_id='+settings.FITBIT_CLIENT_ID+'&scope=activity%20nutrition%20heartrate%20location%20nutrition%20profile%20settings%20sleep%20social%20weight'
            context['auth_url'] = auth_url
            return render(request, 'main/googlefit.html',
                        context=context)
        
        return redirect("/dashboard")

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
