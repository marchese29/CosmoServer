from typing import Literal

from pydantic import BaseModel, Field


class CosmoRequest(BaseModel):
    """Request to the Cosmo server"""

    message: str


class CosmoResponse(BaseModel):
    """Response from the cosmo server"""

    metadata: str | None = Field(
        description="Any additional information about the request", default=None
    )
    response: str | Literal[True] = Field(
        description=(
            "The response to provide to the user.  If a string is provided this is read "
            "aloud, if boolean 'True' then a simple success chime is played."
        )
    )
