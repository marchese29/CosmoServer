from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..database.models import Action as ActionModel
from ..database.models import Plugin as PluginModel
from ..database.models import Rule as RuleModel
from ..models.actions import Action, ActionCreate, ActionUpdate
from ..models.plugins import Plugin, PluginCreate, PluginUpdate
from ..models.rules import Rule, RuleCreate, RuleCreateWithAction, RuleUpdate
from ..plugins.utils import PluginDependencyConflictError, test_plugin_dependencies

router = APIRouter(tags=["CRUD"])


# Action CRUD operations
@router.post("/actions/", response_model=Action)
def create_action(action: ActionCreate, db: Session = Depends(get_db)):
    """Create a new action."""
    db_action = ActionModel(**action.model_dump())
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action


@router.get("/actions/", response_model=list[Action])
def list_actions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all actions."""
    actions = db.query(ActionModel).offset(skip).limit(limit).all()
    return actions


@router.get("/actions/{action_id}", response_model=Action)
def get_action(action_id: str, db: Session = Depends(get_db)):
    """Get a specific action by ID."""
    action = db.query(ActionModel).filter(ActionModel.id == action_id).first()
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.put("/actions/{action_id}", response_model=Action)
def update_action(action_id: str, action: ActionUpdate, db: Session = Depends(get_db)):
    """Update an action."""
    db_action = db.query(ActionModel).filter(ActionModel.id == action_id).first()
    if db_action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    for field, value in action.model_dump().items():
        setattr(db_action, field, value)

    db.commit()
    db.refresh(db_action)
    return db_action


@router.delete("/actions/{action_id}")
def delete_action(action_id: str, db: Session = Depends(get_db)):
    """Delete an action."""
    db_action = db.query(ActionModel).filter(ActionModel.id == action_id).first()
    if db_action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    # Check if any rules are using this action
    rules_using_action = (
        db.query(RuleModel).filter(RuleModel.action_id == action_id).count()
    )
    if rules_using_action > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete action: {rules_using_action} rules are using it",
        )

    db.delete(db_action)
    db.commit()
    return {"message": "Action deleted successfully"}


# Rule CRUD operations
@router.post("/rules/", response_model=Rule)
def create_rule(rule: RuleCreate, db: Session = Depends(get_db)):
    """Create a new rule."""
    # Verify that the action exists
    action = db.query(ActionModel).filter(ActionModel.id == rule.action_id).first()
    if action is None:
        raise HTTPException(status_code=400, detail="Action not found")

    db_rule = RuleModel(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


@router.get("/rules/", response_model=list[Rule])
def list_rules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all rules with their associated actions."""
    rules = db.query(RuleModel).offset(skip).limit(limit).all()
    return rules


@router.get("/rules/{rule_id}", response_model=Rule)
def get_rule(rule_id: str, db: Session = Depends(get_db)):
    """Get a specific rule by ID with its associated action."""
    rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/rules/{rule_id}", response_model=Rule)
def update_rule(rule_id: str, rule: RuleUpdate, db: Session = Depends(get_db)):
    """Update a rule."""
    db_rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if db_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Verify that the action exists if action_id is being updated
    if rule.action_id != db_rule.action_id:
        action = db.query(ActionModel).filter(ActionModel.id == rule.action_id).first()
        if action is None:
            raise HTTPException(status_code=400, detail="Action not found")

    for field, value in rule.model_dump().items():
        setattr(db_rule, field, value)

    db.commit()
    db.refresh(db_rule)
    return db_rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    """Delete a rule."""
    db_rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if db_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(db_rule)
    db.commit()
    return {"message": "Rule deleted successfully"}


# Plugin CRUD operations
@router.post("/plugins/", response_model=Plugin)
async def create_plugin(plugin: PluginCreate, db: Session = Depends(get_db)):
    """Create a new plugin with dependency conflict detection."""
    # Create plugin record but don't commit yet
    db_plugin = PluginModel(**plugin.model_dump())
    db.add(db_plugin)

    # Test dependencies with new plugin included
    try:
        await test_plugin_dependencies(db)
    except PluginDependencyConflictError as e:
        # Rollback and raise HTTP 409 Conflict
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Plugin dependency conflict: {str(e)}"
        ) from e

    # If testing passed, commit the plugin
    db.commit()
    db.refresh(db_plugin)
    return db_plugin


@router.get("/plugins/", response_model=list[Plugin])
def list_plugins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all plugins."""
    plugins = db.query(PluginModel).offset(skip).limit(limit).all()
    return plugins


@router.get("/plugins/{plugin_id}", response_model=Plugin)
def get_plugin(plugin_id: str, db: Session = Depends(get_db)):
    """Get a specific plugin by ID."""
    plugin = db.query(PluginModel).filter(PluginModel.id == plugin_id).first()
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


@router.put("/plugins/{plugin_id}", response_model=Plugin)
async def update_plugin(
    plugin_id: str, plugin: PluginUpdate, db: Session = Depends(get_db)
):
    """Update a plugin with version conflict detection."""
    db_plugin = db.query(PluginModel).filter(PluginModel.id == plugin_id).first()
    if db_plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Only allow updating specific fields for safety
    update_data = plugin.model_dump(exclude_unset=True)

    # Apply updates to the model but don't commit yet
    for field, value in update_data.items():
        setattr(db_plugin, field, value)

    # Test dependencies if version was updated
    if "updated_version" in update_data and update_data["updated_version"]:
        try:
            await test_plugin_dependencies(db)
        except PluginDependencyConflictError as e:
            # Rollback and raise HTTP 409 Conflict
            db.rollback()
            raise HTTPException(
                status_code=409, detail=f"Version conflict: {str(e)}"
            ) from e

    # If testing passed (or no version change), commit the update
    db.commit()
    db.refresh(db_plugin)
    return db_plugin


@router.delete("/plugins/{plugin_id}")
def delete_plugin(plugin_id: str, db: Session = Depends(get_db)):
    """Delete a plugin."""
    db_plugin = db.query(PluginModel).filter(PluginModel.id == plugin_id).first()
    if db_plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # TODO: Implement plugin cleanup logic
    # This would handle:
    # - Removing from bundled environment
    # - Cleaning up plugin files from disk
    # - Unregistering plugin routes and services
    if False:  # This will be replaced with actual cleanup logic
        raise NotImplementedError("Plugin cleanup not yet implemented")

    db.delete(db_plugin)
    db.commit()
    return {"message": "Plugin deleted successfully"}


# Convenience endpoint
@router.post("/rules/create-with-action/", response_model=Rule)
def create_rule_with_action(
    rule_data: RuleCreateWithAction, db: Session = Depends(get_db)
):
    """Create a new rule with a new action."""
    # Create the action
    db_action = ActionModel(**rule_data.action.model_dump())
    db.add(db_action)

    # Create the rule and set the action relationship
    rule_dict = rule_data.model_dump(exclude={"action"})
    db_rule = RuleModel(**rule_dict)
    db_rule.action = db_action

    db.add(db_rule)

    db.commit()
    db.refresh(db_action)
    db.refresh(db_rule)

    return db_rule
