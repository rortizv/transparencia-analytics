from sodapy import Socrata

from transparencia.config import settings


def get_client() -> Socrata:
    return Socrata(
        settings.socrata_domain,
        settings.socrata_app_token or None,
    )
