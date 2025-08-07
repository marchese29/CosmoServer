"""CosmoUtils - Utility class providing access to server internals."""

from typing import Any

from cosmoserver.database import SessionLocal
from cosmoserver.database.prefs import Preferences


class CosmoUtils:
    """Utility class providing access to CosmoServer internals for rules."""

    def preferences(self) -> dict[str, Any]:
        """Get all preferences as a dictionary.

        Returns:
            Dictionary containing all preference key-value pairs
        """
        session = SessionLocal()
        try:
            prefs = Preferences(session)
            return prefs.get_all()
        finally:
            session.close()
