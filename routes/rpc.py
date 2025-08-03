"""Remote procedure call endpoints for rule management operations."""

from cosmo.rules.manager import RuleManager
from cosmo.rules.model import TimerRule, TriggerRule
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from database import get_db
from database.models import Action as ActionModel
from database.models import Rule as RuleModel
from exec_utils import (
    compile_action_function,
    compile_time_provider,
    compile_trigger_function,
    detect_rule_type,
)
from models.rules import (
    InstalledRule,
    InstalledRuleAction,
    InstalledRulesResponse,
    OrphanedRule,
    Rule,
)

router = APIRouter(tags=["RPC"])


def get_rule_manager() -> RuleManager:
    """Dependency to get the rule manager instance."""
    from main import RULE_MANAGER

    return RULE_MANAGER.get()


@router.post("/rules/{rule_id}/install")
def install_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    rule_manager: RuleManager = Depends(get_rule_manager),
):
    """Install a database rule into the rule manager for execution.

    Args:
        rule_id: The ID of the rule to install
        db: Database session
        rule_manager: Rule manager instance

    Returns:
        Success message with installation details

    Raises:
        HTTPException: If rule not found, compilation fails, or installation fails
    """
    # Fetch the rule and its associated action from the database
    db_rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()

    if db_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    if db_rule.action is None:
        raise HTTPException(status_code=400, detail="Rule has no associated action")

    try:
        # Compile the action code into a callable function
        action_routine = compile_action_function(db_rule.action.action_code)

        # Detect the rule type and compile the appropriate trigger/timer function
        rule_type = detect_rule_type(db_rule.trigger)

        if rule_type == "trigger":
            # Compile trigger function and create TriggerRule
            trigger_provider = compile_trigger_function(db_rule.trigger)
            rule_obj = TriggerRule(action_routine, trigger_provider)

            # Install the trigger rule with the database rule ID as task ID
            task = rule_manager.install_trigger_rule(rule_obj, task_id=rule_id)

        elif rule_type == "timer":
            # Compile time provider function and create TimerRule
            time_provider = compile_time_provider(db_rule.trigger)
            rule_obj = TimerRule(action_routine, time_provider)

            # Install the timer rule with the database rule ID as task ID
            task = rule_manager.install_timed_rule(rule_obj, task_id=rule_id)

        else:
            raise HTTPException(status_code=400, detail=f"Unknown rule type: {rule_type}")

        # If the rule is suspended, mark it as suspended in the rule manager
        if db_rule.is_suspended:
            rule_manager.suspend_rule(rule_id)

        return {
            "message": f"Rule '{db_rule.name}' installed successfully",
            "rule_id": rule_id,
            "rule_type": rule_type,
            "task_name": task.get_name(),
            "is_suspended": db_rule.is_suspended,
        }

    except NotImplementedError as e:
        raise HTTPException(
            status_code=501, detail=f"Code compilation not yet implemented: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to install rule: {str(e)}"
        ) from e


@router.post("/rules/{rule_id}/uninstall")
def uninstall_rule(
    rule_id: str,
    rule_manager: RuleManager = Depends(get_rule_manager),
):
    """Uninstall a rule from the rule manager.

    Args:
        rule_id: The ID of the rule to uninstall
        rule_manager: Rule manager instance

    Returns:
        Success message with uninstallation details

    Raises:
        HTTPException: If rule is not currently installed
    """
    try:
        # Attempt to uninstall the rule using the rule_id as task_id
        success = rule_manager.uninstall_rule(rule_id)

        if success:
            return {
                "message": f"Rule with ID '{rule_id}' uninstalled successfully",
                "rule_id": rule_id,
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Rule with ID '{rule_id}' is not currently installed",
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to uninstall rule: {str(e)}"
        ) from e


@router.get("/rules/installed", response_model=InstalledRulesResponse)
def list_installed_rules(
    status_filter: str | None = None,
    rule_manager: RuleManager = Depends(get_rule_manager),
    db: Session = Depends(get_db),
):
    """List all currently installed rules with their complete details.

    Args:
        status_filter: Optional filter by suspension status.
                      "suspended" for only suspended rules,
                      "running" for only non-suspended rules,
                      "orphaned" for only orphaned rules (running but not in database),
                      None for all rules (default)
    """
    try:
        # Validate status_filter parameter
        if status_filter is not None and status_filter not in [
            "suspended",
            "running",
            "orphaned",
        ]:
            raise HTTPException(
                status_code=400,
                detail=(
                    "status_filter must be 'suspended', 'running', 'orphaned', or None"
                ),
            )

        # Get all rule IDs from RuleManager
        installed_rule_ids = rule_manager.get_all_rules()

        if not installed_rule_ids:
            message = "No rules currently installed"
            if status_filter:
                message = f"No {status_filter} rules currently installed"
            return InstalledRulesResponse(message=message, installed_rules=[])

        # Single batch query with eager loading for actions
        db_rules = (
            db.query(RuleModel)
            .options(joinedload(RuleModel.action))
            .filter(RuleModel.id.in_(installed_rule_ids))
            .all()
        )

        # Create mapping from rule_id to database rule
        rule_mapping = {db_rule.id: db_rule for db_rule in db_rules}

        # Build response list
        installed_rules = []
        for rule_id in installed_rule_ids:
            if rule_id in rule_mapping:
                db_rule = rule_mapping[rule_id]

                # Build action data if available
                action_data = None
                if db_rule.action:
                    action_data = InstalledRuleAction(
                        id=db_rule.action.id,
                        name=db_rule.action.name,
                        description=db_rule.action.description,
                        action_code=db_rule.action.action_code,
                    )

                rule_item = InstalledRule(
                    rule_id=db_rule.id,
                    name=db_rule.name,
                    description=db_rule.description,
                    trigger=db_rule.trigger,
                    is_suspended=db_rule.is_suspended,
                    action=action_data,
                )

                # Apply filtering for database rules
                if status_filter is None:
                    installed_rules.append(rule_item)
                elif status_filter == "suspended" and db_rule.is_suspended:
                    installed_rules.append(rule_item)
                elif status_filter == "running" and not db_rule.is_suspended:
                    installed_rules.append(rule_item)
                # Exclude database rules when filtering for orphaned rules
            else:
                # Orphaned task - include if no filter or specifically requesting orphaned
                if status_filter is None or status_filter == "orphaned":
                    installed_rules.append(OrphanedRule(rule_id=rule_id))

        # Generate appropriate message
        if status_filter is None:
            message = "Currently installed rules"
        else:
            message = f"Currently installed {status_filter} rules"

        return InstalledRulesResponse(message=message, installed_rules=installed_rules)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list installed rules: {str(e)}"
        ) from e


@router.post("/rules/{rule_id}/suspend", response_model=Rule)
def suspend_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    rule_manager: RuleManager = Depends(get_rule_manager),
):
    """Suspend a rule from executing its actions.

    Args:
        rule_id: The ID of the rule to suspend
        db: Database session
        rule_manager: Rule manager instance

    Returns:
        The updated rule object

    Raises:
        HTTPException: If rule not found or suspension fails
    """
    # Fetch the rule from the database
    db_rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()

    if db_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    if db_rule.is_suspended:
        raise HTTPException(status_code=400, detail="Rule is already suspended")

    try:
        # Update database
        db_rule.is_suspended = True
        db.commit()
        db.refresh(db_rule)

        # Update rule manager if rule is currently installed
        rule_manager.suspend_rule(rule_id)

        return db_rule

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to suspend rule: {str(e)}"
        ) from e


@router.post("/rules/{rule_id}/resume", response_model=Rule)
def resume_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    rule_manager: RuleManager = Depends(get_rule_manager),
):
    """Resume a suspended rule.

    Args:
        rule_id: The ID of the rule to resume
        db: Database session
        rule_manager: Rule manager instance

    Returns:
        The updated rule object

    Raises:
        HTTPException: If rule not found or resumption fails
    """
    # Fetch the rule from the database
    db_rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()

    if db_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    if not db_rule.is_suspended:
        raise HTTPException(status_code=400, detail="Rule is not suspended")

    try:
        # Update database
        db_rule.is_suspended = False
        db.commit()
        db.refresh(db_rule)

        # Update rule manager if rule is currently installed
        rule_manager.resume_rule(rule_id)

        return db_rule

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to resume rule: {str(e)}"
        ) from e


@router.post("/actions/{action_id}/invoke")
async def invoke_action(
    action_id: str,
    db: Session = Depends(get_db),
    rule_manager: RuleManager = Depends(get_rule_manager),
):
    """Invoke an action directly by its ID.

    Args:
        action_id: The ID of the action to invoke
        db: Database session
        rule_manager: Rule manager instance

    Returns:
        Success message with execution details

    Raises:
        HTTPException: If action not found, compilation fails, or execution fails
    """
    # Fetch the action from the database
    db_action = db.query(ActionModel).filter(ActionModel.id == action_id).first()

    if db_action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    try:
        # Compile the action code into a callable function
        action_routine = compile_action_function(db_action.action_code)

        # Execute the action once using RuleManager
        await rule_manager.run_action_once(action_routine)

        return {
            "message": f"Action '{db_action.name}' executed successfully",
            "action_id": action_id,
            "action_name": db_action.name,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Action execution failed: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to execute action: {str(e)}"
        ) from e
