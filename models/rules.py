from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.actions import Action, ActionCreate


class RuleBase(BaseModel):
    """Base schema for Rule with common fields."""

    name: str
    description: str
    trigger: str


class RuleCreate(RuleBase):
    """Schema for creating a new Rule with existing action."""

    action_id: str


class RuleUpdate(RuleBase):
    """Schema for updating a Rule."""

    action_id: str


class Rule(RuleBase):
    """Schema for Rule responses with full details."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    action_id: str
    created_at: datetime
    updated_at: datetime
    action: Action | None = None


class RuleCreateWithAction(RuleBase):
    """Convenience schema for creating a Rule with a new Action."""

    action: ActionCreate
