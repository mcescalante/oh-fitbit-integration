from ohapi import api
from django.conf import settings

def get_fitbit_file(oh_member):
    try:
        oh_access_token = oh_member.get_access_token(
                                client_id=settings.OPENHUMANS_CLIENT_ID,
                                client_secret=settings.OPENHUMANS_CLIENT_SECRET)
        user_object = api.exchange_oauth2_member(oh_access_token)
        for dfile in user_object['data']:
            if 'Fitbit' in dfile['metadata']['tags']:
                return dfile['download_url']
        return ''

    except:
        return 'error'