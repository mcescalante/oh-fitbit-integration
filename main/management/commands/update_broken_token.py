from django.core.management.base import BaseCommand
from main.models import FitbitMember
from open_humans.models import OpenHumansMember
from datauploader.tasks import fetch_fitbit_data
# from fitbit.settings import OPENHUMANS_CLIENT_ID, OPENHUMANS_CLIENT_SECRET
from django.conf import settings

class Command(BaseCommand):
    help = 'Refresh Fitbit tokens that were previously broken'

    def add_arguments(self, parser):
        parser.add_argument('--infile', type=str,
                            help='CSV with project_member_id & refresh_token')
        parser.add_argument('--delimiter', type=str,
                            help='CSV delimiter')

    def handle(self, *args, **options):
        for line in open(options['infile']):
            if not line.startswith('proj_member_id'):
                line = line.strip().split(options['delimiter'])
                oh_id = line[0]
                oh_refresh_token = line[1]
                fitbit_refresh_token = line[2]
                if len(OpenHumansMember.objects.filter(
                            oh_id=oh_id)) == 1:
                    oh_member = OpenHumansMember.get(oh_id=oh_id)
                    fitbit_member = oh_member.fitbit_member
                    print(fitbit_member)
                    successful_refresh = fitbit_member._refresh_tokens()
                    if not successful_refresh:
                        fitbit_member.refresh_token = fitbit_refresh_token
                        fitbit_member.save()
                        fitbit_member._refresh_tokens()
                    # fetch_fitbit_data.delay(oh_member.oh_id, oh_member.fitbit_member.access_token)
