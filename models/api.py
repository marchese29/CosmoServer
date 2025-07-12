from pydantic import BaseModel


class CosmoRequest(BaseModel):
    """Request to the Cosmo server"""

    message: str
