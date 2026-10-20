"""Account lookups for the SMTP server."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import get_account_by_email


def user_exists(email: str) -> bool:
    """Return whether an address belongs to a registered local account."""
    return get_account_by_email(email) is not None
