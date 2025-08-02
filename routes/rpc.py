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

        return {
            "message": f"Rule '{db_rule.name}' installed successfully",
            "rule_id": rule_id,
            "rule_type": rule_type,
            "task_name": task.get_name(),
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
    rule_manager: RuleManager = Depends(get_rule_manager),
    db: Session = Depends(get_db),
):
    """List all currently installed rules with their complete details."""
    try:
        # Get all rule IDs from RuleManager
        installed_rule_ids = rule_manager.get_all_rules()

        if not installed_rule_ids:
            return InstalledRulesResponse(
                message="No rules currently installed", installed_rules=[]
            )

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

                installed_rules.append(
                    InstalledRule(
                        rule_id=db_rule.id,
                        name=db_rule.name,
                        description=db_rule.description,
                        trigger=db_rule.trigger,
                        action=action_data,
                    )
                )
            else:
                # Orphaned task
                installed_rules.append(OrphanedRule(rule_id=rule_id))

        return InstalledRulesResponse(
            message="Currently installed rules", installed_rules=installed_rules
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list installed rules: {str(e)}"
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
