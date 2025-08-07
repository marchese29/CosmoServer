"""CosmoUtils - Utility class providing access to server internals."""

from typing import Any

from cosmoserver.database import SessionLocal
from cosmoserver.database.globals import GlobalVariables
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

    def set_global(self, key: str, value: Any) -> None:
        """Set a global variable value.

        Args:
            key: The variable key (string)
            value: The variable value (must be JSON serializable)

        Raises:
            ValueError: If the value is not JSON serializable
        """
        session = SessionLocal()
        try:
            globals_manager = GlobalVariables(session)
            globals_manager.set(key, value)
        finally:
            session.close()

    def get_global(self, key: str) -> Any | None:
        """Get a global variable value.

        Args:
            key: The variable key (string)

        Returns:
            The variable value, or None if not set
        """
        session = SessionLocal()
        try:
            globals_manager = GlobalVariables(session)
            return globals_manager.get(key)
        finally:
            session.close()

    def is_global_set(self, key: str) -> bool:
        """Check if a global variable is set (exists in the database).

        Args:
            key: The variable key (string)

        Returns:
            True if the variable exists, False otherwise
        """
        session = SessionLocal()
        try:
            globals_manager = GlobalVariables(session)
            return globals_manager.exists(key)
        finally:
            session.close()

    def delete_global(self, key: str) -> bool:
        """Delete a global variable.

        Args:
            key: The variable key (string)

        Returns:
            True if the variable was deleted, False if it didn't exist
        """
        session = SessionLocal()
        try:
            globals_manager = GlobalVariables(session)
            return globals_manager.delete(key)
        finally:
            session.close()
