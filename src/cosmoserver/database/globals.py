"""Database global variables system."""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import GlobalVariable


class GlobalVariables:
    """Class for managing global variables with JSON serialization."""

    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session

    def get(self, key: str) -> Any | None:
        """Get global variable value, returns None if not set."""
        stmt = select(GlobalVariable).where(GlobalVariable.key == key)
        result = self.session.scalar(stmt)
        return result.value if result else None

    def set(self, key: str, value: Any) -> None:
        """Set global variable value (must be JSON serializable)."""
        # Validate that the value is JSON serializable
        try:
            json.dumps(value)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Value for key '{key}' is not JSON serializable: {e}"
            ) from e

        # Check if global variable already exists
        stmt = select(GlobalVariable).where(GlobalVariable.key == key)
        existing = self.session.scalar(stmt)

        if existing:
            existing.value = value
        else:
            new_var = GlobalVariable(key=key, value=value)
            self.session.add(new_var)

        self.session.commit()

    def delete(self, key: str) -> bool:
        """Delete global variable, return True if existed."""
        stmt = select(GlobalVariable).where(GlobalVariable.key == key)
        existing = self.session.scalar(stmt)

        if existing:
            self.session.delete(existing)
            self.session.commit()
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if global variable is set."""
        stmt = select(GlobalVariable).where(GlobalVariable.key == key)
        result = self.session.scalar(stmt)
        return result is not None

    def get_all(self) -> dict[str, Any]:
        """Get all global variables as a dictionary."""
        stmt = select(GlobalVariable)
        results = self.session.scalars(stmt).all()
        return {var.key: var.value for var in results}
