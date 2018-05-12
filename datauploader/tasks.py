"""
Asynchronous tasks that update data in Open Humans.
These tasks:
  1. delete any current files in OH if they match the planned upload filename
  2. adds a data file
"""
import logging
import os
import json
import shutil
import tempfile
import requests
import arrow
from celery import shared_task
from django.conf import settings
from open_humans.models import OpenHumansMember
from datetime import datetime
from fitbit.settings import rr
from main.models import FitbitMember
from ohapi import api
from requests_respectful import (RespectfulRequester,
                                 RequestsRespectfulRateLimitedError)

# Set up logging.
logger = logging.getLogger(__name__)


# TODO: we don't need this, we should ideally re-queue a request that hits the exception.
class RateLimitException(Exception):
    """
    An exception that is raised if we reach a request rate cap.
    """

    # TODO: add the source of the rate limit we hit for logging (fitit,
    # internal global fitbit, internal user-specific fitbit)

    pass

@shared_task
def fetch_fitbit_data(fitbit_member_id, access_token):
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
    print("entered function")

    # Get Fitbit member object
    fitbit_member = FitbitMember.objects.get(id=fitbit_member_id)
    # Refresh fitbit and OH tokens
    # fitbit_member._refresh_tokens()
    # fitbit_member.user._refresh_tokens()
    # Get user again so we have updated tokens and not the original ones
    # fitbit_member = FitbitMember.objects.get(id=fitbit_member_id)

    # Get existing data as currently stored on OH
    fitbit_data = get_existing_fitbit(fitbit_member.user.access_token,
                                      fitbit_urls)

    # Set up user realm since rate limiting is per-user
    print(fitbit_member.user)
    user_realm = 'fitbit-{}'.format(fitbit_member.user.oh_id)
    rr.register_realm(user_realm, max_requests=150, timespan=3600)
    rr.update_realm(user_realm, max_requests=150, timespan=3600)

    # Get initial information about user from Fitbit
    print("Creating header and going to get user profile")
    headers = {'Authorization': "Bearer %s" % fitbit_member.access_token}
    query_result = requests.get('https://api.fitbit.com/1/user/-/profile.json', headers=headers).json()

    # Store the user ID since it's used in all future queries
    user_id = query_result['user']['encodedId']
    member_since = query_result['user']['memberSince']
    start_date = arrow.get(member_since, 'YYYY-MM-DD')
    # if not fitbit_data:
    #     start_date = arrow.get(member_since, 'YYYY-MM-DD')

    print(query_result)

    # fitbit_data = {}
    # print(fitbit_data)

    # Refresh token if the result is 401
    # TODO: update this so it just checks the expired field.
    # if query_result.status_code == 401:
    #     fitbit_member._refresh_tokens()

    if not fitbit_data:
        print("empty data")
        # fitbit_data = {}
        # return

    # Reset data if user account ID has changed.
    print("reset data if user account ID changed")
    if 'profile' in fitbit_data:
        if fitbit_data['profile']['encodedId'] != user_id:
            logging.info(
                'User ID changed from {} to {}. Resetting all data.'.format(
                    fitbit_data['profile']['encodedId'], user_id))
            fitbit_data = {}
            for url in fitbit_urls:
                fitbit_data[url['name']] = {}
        else:
            logging.debug('User ID ({}) matches old data.'.format(user_id))

    fitbit_data['profile'] = {
        'averageDailySteps': query_result['user']['averageDailySteps'],
        'encodedId': user_id,
        'height': query_result['user']['height'],
        'memberSince': member_since,
        'strideLengthRunning': query_result['user']['strideLengthRunning'],
        'strideLengthWalking': query_result['user']['strideLengthWalking'],
        'weight': query_result['user']['weight']
    }

    print("entering try block")
    try:
        # Some block about if the period is none
        print("period none")
        for url in [u for u in fitbit_urls if u['period'] is None]:
            if not user_id and 'profile' in fitbit_data:
                user_id = fitbit_data['profile']['user']['encodedId']

            # Build URL
            fitbit_api_base_url = 'https://api.fitbit.com/1/user'
            final_url = fitbit_api_base_url + url['url'].format(user_id=user_id)
            # Fetch the data
            print(final_url)
            r = rr.get(url=final_url,
                    headers=headers,
                    realms=["Fitbit", 'fitbit-{}'.format(fitbit_member.user.oh_id)])
            print(r.text)

            # print(fitbit_data)
            fitbit_data[url['name']] = r.json()

        #Period year URLs
        print("period year")
        # print(fitbit_data)
        for url in [u for u in fitbit_urls if u['period'] == 'year']:
            # print("LOOPED OVER A URL" + str(url))
            years = arrow.Arrow.range('year', start_date.floor('year'),
                                    arrow.get())
            # print(years)
            for year_date in years:
                # print(year_date)
                year = year_date.format('YYYY')

                if year in fitbit_data[url['name']]:
                    logger.info('Skip retrieval {}: {}'.format(url['name'], year))
                    continue

                logger.info('Retrieving %s: %s', url['name'], year)
                # Build URL
                fitbit_api_base_url = 'https://api.fitbit.com/1/user'
                final_url = fitbit_api_base_url + url['url'].format(user_id=user_id,
                                                                    start_date=year_date.floor('year').format('YYYY-MM-DD'),
                                                                    end_date=year_date.ceil('year').format('YYYY-MM-DD'))
                # Fetch the data
                print(final_url)
                r = rr.get(url=final_url,
                        headers=headers,
                        realms=["Fitbit", 'fitbit-{}'.format(fitbit_member.user.oh_id)])

                # print([url['name']]['blah'])
                # print([str(year)])
                fitbit_data[url['name']][str(year)] = r.json()

        # Month period URLs/fetching
        # print(fitbit_data)
        print("period month")
        for url in [u for u in fitbit_urls if u['period'] == 'month']:
            months = arrow.Arrow.range('month', start_date.floor('month'),
                                    arrow.get())
            for month_date in months:
                month = month_date.format('YYYY-MM')

                if month in fitbit_data[url['name']]:
                    logger.info('Skip retrieval {}: {}'.format(url['name'], month))
                    continue

                logger.info('Retrieving %s: %s', url['name'], month)
                # Build URL
                fitbit_api_base_url = 'https://api.fitbit.com/1/user'
                final_url = fitbit_api_base_url + url['url'].format(user_id=user_id,
                                                                    start_date=month_date.floor('month').format('YYYY-MM-DD'),
                                                                    end_date=month_date.ceil('month').format('YYYY-MM-DD'))
                # Fetch the data
                print(final_url)
                r = rr.get(url=final_url,
                        headers=headers,
                        realms=["Fitbit", 'fitbit-{}'.format(fitbit_member.user.oh_id)])

                fitbit_data[url['name']][month] = r.json()

    except RequestsRespectfulRateLimitedError:
        logging.info('Requests-respectful reports rate limit hit.')
        print("hit requests respectful rate limit, going to requeue")
        fetch_fitbit_data.apply_async(args=[fitbit_member_id, fitbit_member.user.access_token], countdown=3600)
        # raise RateLimitException()
    finally:
        print("calling finally")
        # print(fitbit_data)
        replace_fitbit(fitbit_member.user, fitbit_data)

    # return fitbit_data


def get_existing_fitbit(oh_access_token, fitbit_urls):
    print("entered get_existing_fitbit")
    member = api.exchange_oauth2_member(oh_access_token)
    for dfile in member['data']:
        if 'Fitbit' in dfile['metadata']['tags']:
            print("got inside fitbit if")
            # get file here and read the json into memory
            tf_in = tempfile.NamedTemporaryFile(suffix='.json')
            tf_in.write(requests.get(dfile['download_url']).content)
            tf_in.flush()
            fitbit_data = json.load(open(tf_in.name))
            print("fetched existing data from OH")
            # print(fitbit_data)
            return fitbit_data
    fitbit_data = {}
    for url in fitbit_urls:
        fitbit_data[url['name']] = {}
    return fitbit_data


def replace_fitbit(oh_member, fitbit_data):
    print("replace function started")
    # delete old file and upload new to open humans
    tmp_directory = tempfile.mkdtemp()
    metadata = {
        'description':
        'Fitbit data.',
        'tags': ['Fitbit', 'activity', 'steps'],
        'updated_at': str(datetime.utcnow()),
        }
    out_file = os.path.join(tmp_directory, 'fitbit-data.json')
    logger.debug('deleted old file for {}'.format(oh_member.oh_id))
    deleter = api.delete_file(oh_member.access_token,
                    oh_member.oh_id,
                    file_basename="fitbit-data.json")
    print("delete response")
    print(deleter)
    print("trying to write to file")
    with open(out_file, 'w') as json_file:
        print("inside open file")
        # json.dump(fitbit_data, json_file)
        json_file.write(json.dumps(fitbit_data))
        # print(json.dump(fitbit_data, json_file))
        print("dumped, trying to flush")
        json_file.flush()
    print("attempting add response")
    addr = api.upload_aws(out_file, metadata,
                   oh_member.access_token,
                   project_member_id=oh_member.oh_id)
    print("add response")
    print(addr)
    logger.debug('uploaded new file for {}'.format(oh_member.oh_id))


@shared_task
def xfer_to_open_humans(user_data, metadata, oh_id, num_submit=0, **kwargs):
    """
    Transfer data to Open Humans.
    num_submit is an optional parameter in case you want to resubmit failed
    tasks (see comments in code).
    """

    logger.debug('Trying to copy data for {} to Open Humans'.format(oh_id))

    oh_member = OpenHumansMember.objects.get(oh_id=oh_id)

    # Make a tempdir for all temporary files.
    # Delete this even if an exception occurs.
    tempdir = tempfile.mkdtemp()
    try:
        add_data_to_open_humans(user_data, metadata, oh_member, tempdir)
    finally:
        shutil.rmtree(tempdir)

    # Note: Want to re-run tasks in case of a failure?
    # You can resubmit a task by calling it again. (Be careful with recursion!)
    # e.g. to give up, resubmit, & try again after 10s if less than 5 attempts:
    # if num_submit < 5:
    #     num_submit += 1
    #     xfer_to_open_humans.apply_async(
    #         args=[oh_id, num_submit], kwargs=kwargs, countdown=10)
    #     return


def add_data_to_open_humans(user_data, metadata, oh_member, tempdir):
    """
    Add demonstration file to Open Humans.
    This might be a good place to start editing, to add your own project data.
    This template is written to provide the function with a tempdir that
    will be cleaned up later. You can use the tempdir to stage the creation of
    files you plan to upload to Open Humans.
    """
    # Create data file.
    data_filepath, data_metadata = make_datafile(user_data, metadata, tempdir)

    # Remove any files with this name previously added to Open Humans.
    delete_oh_file_by_name(oh_member, filename=os.path.basename(data_filepath))

    # Upload this file to Open Humans.
    upload_file_to_oh(oh_member, data_filepath, data_metadata)


def make_datafile(user_data, metadata, tempdir):
    """
    Make a user data file in the tempdir.
    """
    filename = 'user_data_' + datetime.today().strftime('%Y%m%d')
    filepath = os.path.join(tempdir, filename)

    with open(filepath, 'w') as f:
        f.write(user_data)

    return filepath, metadata


def delete_oh_file_by_name(oh_member, filename):
    """
    Delete all project files matching the filename for this Open Humans member.
    This deletes files this project previously added to the Open Humans
    member account, if they match this filename. Read more about file deletion
    API options here:
    https://www.openhumans.org/direct-sharing/oauth2-data-upload/#deleting-files
    """
    req = requests.post(
        settings.OH_DELETE_FILES,
        params={'access_token': oh_member.get_access_token()},
        data={'project_member_id': oh_member.oh_id,
              'file_basename': filename})
    req.raise_for_status()


def upload_file_to_oh(oh_member, filepath, metadata):
    """
    This demonstrates using the Open Humans "large file" upload process.
    The small file upload process is simpler, but it can time out. This
    alternate approach is required for large files, and still appropriate
    for small files.
    This process is "direct to S3" using three steps: 1. get S3 target URL from
    Open Humans, 2. Perform the upload, 3. Notify Open Humans when complete.
    """
    # Get the S3 target from Open Humans.
    upload_url = '{}?access_token={}'.format(
        settings.OH_DIRECT_UPLOAD, oh_member.get_access_token())
    req1 = requests.post(
        upload_url,
        data={'project_member_id': oh_member.oh_id,
              'filename': os.path.basename(filepath),
              'metadata': json.dumps(metadata)})
    req1.raise_for_status()

    # Upload to S3 target.
    with open(filepath, 'rb') as fh:
        req2 = requests.put(url=req1.json()['url'], data=fh)
    req2.raise_for_status()

    # Report completed upload to Open Humans.
    complete_url = ('{}?access_token={}'.format(
        settings.OH_DIRECT_UPLOAD_COMPLETE, oh_member.get_access_token()))
    req3 = requests.post(
        complete_url,
        data={'project_member_id': oh_member.oh_id,
              'file_id': req1.json()['id']})
    req3.raise_for_status()

    logger.debug('Upload done: "{}" for member {}.'.format(
            os.path.basename(filepath), oh_member.oh_id))
