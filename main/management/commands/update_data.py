from django.core.management.base import BaseCommand
from main.models import FitbitMember
from main.views import fetch_fitbit_data

class Command(BaseCommand):
    help = 'Updates data for all members'

    def handle(self, *args, **options):
        users = FitbitMember.objects.all()
        for user in users:
            fetch_fitbit_data(user, user.access_token)