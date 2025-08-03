from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.actions import Action, ActionCreate


class RuleBase(BaseModel):
    """Base schema for Rule with common fields."""

    name: str
    description: str
    trigger: str
    is_suspended: bool = False


class RuleCreate(RuleBase):
    """Schema for creating a new Rule with existing action."""

    action_id: str


class RuleUpdate(BaseModel):
    """Schema for updating a Rule."""

    name: str
    description: str
    trigger: str
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


class InstalledRuleAction(BaseModel):
    """Action details for an installed rule."""

    id: str
    name: str
    description: str
    action_code: str


class InstalledRule(BaseModel):
    """Schema for installed rule with full details including action code."""

    rule_id: str
    name: str
    description: str
    trigger: str
    is_suspended: bool = False
    action: InstalledRuleAction | None = None


class OrphanedRule(BaseModel):
    """Schema for orphaned rule (running but not in database)."""

    rule_id: str
    name: str = "Unknown (orphaned task)"
    description: str = "Rule not found in database"
    trigger: str | None = None
    action: InstalledRuleAction | None = None


class InstalledRulesResponse(BaseModel):
    """Response model for listing installed rules."""

    message: str
    installed_rules: list[InstalledRule | OrphanedRule]
