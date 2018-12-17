from django.db import models
from django.conf import settings
from open_humans.models import OpenHumansMember
from datetime import timedelta
import requests
import arrow

import google.oauth2.credentials
import google_auth_oauthlib.flow



class GoogleFitMember(models.Model):
    """
    Store OAuth2 data for a GoogleFit Member.
    This is a one to one relationship with a OpenHumansMember object.
    """
    user = models.OneToOneField(OpenHumansMember, related_name="googlefit_member", on_delete=models.CASCADE)
    userid = models.CharField(max_length=255, unique=True, null=True)
    access_token = models.CharField(max_length=512)
    refresh_token = models.CharField(max_length=512)
    expires_in = models.CharField(max_length=512, default=3600)
    scope = models.CharField(max_length=512)
    token_type = models.CharField(max_length=512)
    last_updated = models.DateTimeField(
                            default=(arrow.now() - timedelta(days=7)).format())
    last_submitted = models.DateTimeField(
                            default=(arrow.now() - timedelta(days=7)).format())

    @staticmethod
    def get_expiration(expires_in):
        return (arrow.now() + timedelta(seconds=expires_in)).format()

    def get_access_token(self):
        """
        Return access token. Refresh first if necessary.
        """
        # Also refresh if nearly expired (less than 60s remaining).
        delta = timedelta(seconds=60)
        if arrow.get(self.expires_in) - delta < arrow.now():
            self._refresh_tokens()
        return self.access_token

    def _refresh_tokens(self):
        """
        Refresh access token.
        """
        credentials = google.oauth2.credentials.Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri=settings.GOOGLEFIT_TOKEN_URI,
            client_id=settings.GOOGLEFIT_CLIENT_ID,
            client_secret=settings.GOOGLEFIT_CLIENT_SECRET,
            scopes=settings.GOOGLEFIT_SCOPES,
        )
        if credentials.valid:
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            self.access_token = credentials.token
            self.refresh_token = credentials.refresh_token
            self.save()
            return True
        return False
