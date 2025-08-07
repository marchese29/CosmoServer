from typing import Any

from pydantic import BaseModel


class PreferenceResponse(BaseModel):
    """Response model for a single preference."""

    key: str
    value: Any


class PreferenceUpdate(BaseModel):
    """Request model for updating a preference value."""

    value: Any
