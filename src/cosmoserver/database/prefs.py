"""Database preferences system with type-safe interface."""

import typing
from collections.abc import Callable
from enum import Enum
from typing import Any

from sqlalchemy import JSON, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .base import Base


def NULL_VALIDATOR(value: object) -> bool:
    """Default validator that accepts any value (no additional validation)."""
    return True


def validate_location(location: list[float]) -> bool:
    """Validate that location is exactly [lat, lon] with proper bounds."""
    return (
        len(location) == 2
        and -90 <= location[0] <= 90  # latitude bounds
        and -180 <= location[1] <= 180  # longitude bounds
    )


class PreferenceKey[T]:
    """Container for preference key metadata including validation."""

    def __init__(
        self,
        key: str,
        value_type: type[T],
        validator: Callable[[T], bool] = NULL_VALIDATOR,
    ):
        self.key = key
        self.value_type = value_type
        self.validator = validator

    def validate(self, value: T) -> bool:
        """Validate a value against both type and custom validation."""
        return self.validator(value)


class PreferenceKeys(Enum):
    """Enum of all available preference keys with their types and validators."""

    # Smart home location as [lat, lon] with validation
    HOME_LOCATION = PreferenceKey("home_location", list[float], validate_location)

    # User's name (uses NULL_VALIDATOR by default)
    USER_NAME = PreferenceKey("user_name", str)


class Preference(Base):
    """SQLAlchemy model for storing preferences."""

    __tablename__ = "preferences"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)


class Preferences:
    """Class for managing preferences with type safety."""

    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session

    def get(self, key: PreferenceKeys) -> Any | None:
        """Get preference value, returns None if not set."""
        stmt = select(Preference).where(Preference.key == key.value.key)
        result = self.session.scalar(stmt)
        return result.value if result else None

    def set(self, key: PreferenceKeys, value: Any) -> None:
        """Set preference value with full validation."""
        pref_key = key.value

        # Get the origin type for generic types (e.g., list from list[float])
        expected_type = typing.get_origin(pref_key.value_type) or pref_key.value_type

        # First check basic type
        if not isinstance(value, expected_type):
            expected_name = getattr(
                pref_key.value_type, "__name__", str(pref_key.value_type)
            )
            actual = type(value).__name__
            raise TypeError(
                f"Invalid type for {pref_key.key}: expected {expected_name}, got {actual}"
            )

        # Then apply custom validation
        if not pref_key.validate(value):  # type: ignore[arg-type]
            raise ValueError(f"Invalid value for {pref_key.key}: {value}")

        # Check if preference already exists
        stmt = select(Preference).where(Preference.key == pref_key.key)
        existing = self.session.scalar(stmt)

        if existing:
            existing.value = value
        else:
            new_pref = Preference(key=pref_key.key, value=value)
            self.session.add(new_pref)

        self.session.commit()

    def delete(self, key: PreferenceKeys) -> bool:
        """Delete preference, return True if existed."""
        stmt = select(Preference).where(Preference.key == key.value.key)
        existing = self.session.scalar(stmt)

        if existing:
            self.session.delete(existing)
            self.session.commit()
            return True
        return False

    def exists(self, key: PreferenceKeys) -> bool:
        """Check if preference is set."""
        stmt = select(Preference).where(Preference.key == key.value.key)
        result = self.session.scalar(stmt)
        return result is not None

    def get_all(self) -> dict[str, Any]:
        """Get all preferences as a dictionary."""
        stmt = select(Preference)
        results = self.session.scalars(stmt).all()
        return {pref.key: pref.value for pref in results}
