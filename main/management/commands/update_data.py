from django.core.management.base import BaseCommand
from main.models import FitbitMember
from open_humans.models import OpenHumansMember
from main.views import fetch_fitbit_data
from fitbit.settings import OPENHUMANS_CLIENT_ID, OPENHUMANS_CLIENT_SECRET
import arrow
from datetime import timedelta

class Command(BaseCommand):
    help = 'Update data for all users'

    def handle(self, *args, **options):
        fitbit_users = FitbitMember.objects.all()
        for user in fitbit_users:
            if user.last_submitted < (arrow.now() - timedelta(days=4)):
                print("running update for user {}".format(user.userid))
                fetch_fitbit_data.delay(user.id, user.access_token)
            else:
                print("didn't update {}".format(user.userid))