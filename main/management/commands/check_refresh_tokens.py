from django.core.management.base import BaseCommand
from main.models import FitbitMember


class Command(BaseCommand):
    help = 'Update data for all users'

    def handle(self, *args, **options):
        for fb in FitbitMember.objects.all():
            print(fb.user.user.oh_member.oh_id)
            fb._refresh_tokens()
