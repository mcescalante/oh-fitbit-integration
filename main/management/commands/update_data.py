from django.core.management.base import BaseCommand
from main.models import FitbitMember
from open_humans.models import OpenHumansMember
from main.views import fetch_fitbit_data
from fitbit.settings import OPENHUMANS_CLIENT_ID, OPENHUMANS_CLIENT_SECRET

class Command(BaseCommand):
    help = 'Update data for all users'

    def handle(self, *args, **options):
      pass