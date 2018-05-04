from django.core.management.base import BaseCommand
from main.models import FitbitMember
from open_humans.models import OpenHumansMember
from datauploader.tasks import fetch_fitbit_data
from fitbit.settings import OPENHUMANS_CLIENT_ID, OPENHUMANS_CLIENT_SECRET

class Command(BaseCommand):
    help = 'Import existing users from legacy project. Refresh (and save) OH/Fitbit tokens for all members'

    def add_arguments(self, parser):
        parser.add_argument('--infile', type=str,
                            help='CSV with project_member_id & refresh_token')
        parser.add_argument('--delimiter', type=str,
                            help='CSV delimiter')

    def handle(self, *args, **options):
        for line in open(options['infile']):
            line = line.strip().split(options['delimiter'])
            oh_id = line[0]
            oh_refresh_token = line[1]
            moves_refresh_token = line[2]
            if len(OpenHumansMember.objects.filter(
                        oh_id=oh_id)) == 0:
                oh_member = OpenHumansMember.create(
                                    oh_id=oh_id,
                                    access_token="mock",
                                    refresh_token=oh_refresh_token,
                                    expires_in=-3600)
                oh_member.save()
                oh_member._refresh_tokens(client_id=settings.OPENHUMANS_CLIENT_ID,
                                            client_secret=settings.OPENHUMANS_CLIENT_SECRET)
                oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
                fitbit_member = FitbitMember(
                    access_token="mock",
                    refresh_token=moves_refresh_token,
                    token_expires=FitbitMember.get_expiration(
                        -3600)
                )
                fitbit_member.user = oh_member
                fitbit_member._refresh_tokens()
                fetch_fitbit_data.delay(oh_member.oh_id, oh_member.fitbit_member.access_token)