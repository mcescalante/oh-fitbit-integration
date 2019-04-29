from ohapi import api
from django.conf import settings
import arrow
from datetime import timedelta


def get_fitbit_file(oh_member):
    try:
        oh_access_token = oh_member.get_access_token(
                                client_id=settings.OPENHUMANS_CLIENT_ID,
                                client_secret=settings.OPENHUMANS_CLIENT_SECRET)
        user_object = api.exchange_oauth2_member(
            oh_access_token, all_files=True)
        for dfile in user_object['data']:
            if 'Fitbit' in dfile['metadata']['tags']:
                return dfile['download_url']
        return ''

    except:
        return 'error'


def check_update(fitbit_member):
    if fitbit_member.last_submitted < (arrow.now() - timedelta(hours=1)):
        return True
    return False
