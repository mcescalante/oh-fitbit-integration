from django.core.management.base import BaseCommand
from main.models import FitbitMember
from open_humans.models import OpenHumansMember
from main.views import fetch_fitbit_data
from fitbit.settings import OPENHUMANS_CLIENT_ID, OPENHUMANS_CLIENT_SECRET

class Command(BaseCommand):
    help = 'Updates data for all members'

    def handle(self, *args, **options):

        #OH token refresh
        users = OpenHumansMember.objects.all()
        for user in users:
            print(user.access_token)
            # print(OPENHUMANS_CLIENT_ID)
            # print(user)
            user._refresh_tokens(OPENHUMANS_CLIENT_ID, OPENHUMANS_CLIENT_SECRET)
            # fetch_fitbit_data(user, user.access_token)