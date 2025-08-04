from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActionBase(BaseModel):
    """Base schema for Action with common fields."""

    name: str
    description: str
    action_code: str


class ActionCreate(ActionBase):
    """Schema for creating a new Action."""

    pass


class ActionUpdate(ActionBase):
    """Schema for updating an Action."""

    pass


class Action(ActionBase):
    """Schema for Action responses with full details."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
