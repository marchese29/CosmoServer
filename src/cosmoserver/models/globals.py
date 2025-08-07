from typing import Any

from pydantic import BaseModel


class GlobalVariableResponse(BaseModel):
    """Response model for a single global variable."""

    key: str
    value: Any


class GlobalVariableUpdate(BaseModel):
    """Request model for updating a global variable value."""

    value: Any
