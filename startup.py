"""Startup utilities for rule management."""

import logging

from cosmo.rules.manager import RuleManager
from cosmo.rules.model import TimerRule, TriggerRule
from sqlalchemy.orm import Session, sessionmaker

from database import engine
from database.models import Rule as RuleModel
from exec_utils import (
    compile_action_function,
    compile_time_provider,
    compile_trigger_function,
    detect_rule_type,
)

logger = logging.getLogger(__name__)


def auto_install_database_rules(rule_manager: RuleManager) -> None:
    """Auto-install all rules from the database into the rule manager.

    Args:
        rule_manager: The RuleManager instance to install rules into
    """
    logger.info("Auto-installing database rules")

    # Create database session to query rules
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = SessionLocal()

    try:
        # Query all rules from database
        rules = db_session.query(RuleModel).all()
        logger.info(f"Found {len(rules)} rules in database")

        installed_count = 0
        for rule in rules:
            try:
                _install_single_rule(rule, rule_manager, db_session)
                logger.info(f"Auto-installed rule: {rule.name}")
                installed_count += 1
            except Exception as e:
                logger.error(f"Failed to auto-install rule '{rule.name}': {e}")

        logger.info(
            f"Auto-installation complete: {installed_count}/{len(rules)} rules installed"
        )

    except Exception as e:
        logger.error(f"Error during rule auto-installation: {e}")
    finally:
        db_session.close()


def _install_single_rule(
    db_rule: RuleModel, rule_manager: RuleManager, db_session: Session
) -> None:
    """Install a single database rule into the rule manager.

    Args:
        db_rule: The database rule model
        rule_manager: The RuleManager instance
        db_session: Database session (for loading related objects)
    """
    if db_rule.action is None:
        raise ValueError(f"Rule '{db_rule.name}' has no associated action")

    # Compile the action code into a callable function
    action_routine = compile_action_function(db_rule.action.action_code)

    # Detect the rule type and compile the appropriate trigger/timer function
    rule_type = detect_rule_type(db_rule.trigger)

    if rule_type == "trigger":
        # Compile trigger function and create TriggerRule
        trigger_provider = compile_trigger_function(db_rule.trigger)
        rule_obj = TriggerRule(action_routine, trigger_provider)

        # Install the trigger rule with the database rule ID as task ID
        rule_manager.install_trigger_rule(rule_obj, task_id=db_rule.id)

    elif rule_type == "timer":
        # Compile time provider function and create TimerRule
        time_provider = compile_time_provider(db_rule.trigger)
        rule_obj = TimerRule(action_routine, time_provider)

        # Install the timer rule with the database rule ID as task ID
        rule_manager.install_timed_rule(rule_obj, task_id=db_rule.id)

    else:
        raise ValueError(f"Unknown rule type: {rule_type}")

    # If the rule is suspended, mark it as suspended in the rule manager
    if db_rule.is_suspended:
        rule_manager.suspend_rule(db_rule.id)
