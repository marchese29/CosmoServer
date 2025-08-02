"""Utilities for executing dynamic code strings and converting them to callables."""

import ast
import inspect
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import cast, get_type_hints

from cosmo.plugin.builtin import CosmoUtils
from cosmo.plugin.model import AbstractCondition
from cosmo.rules.model import RuleRoutine, RuleTimeProvider, RuleTriggerProvider


def _get_safe_namespace() -> dict[str, object]:
    """Create a safe execution namespace with pre-loaded imports.

    Returns:
        Dictionary containing allowed imports and utilities
    """
    from main import PLUGIN_SERVICE

    # Start with standard library and cosmo core types
    namespace = {
        "datetime": datetime,
        "timedelta": timedelta,
        "AbstractCondition": AbstractCondition,
        "CosmoUtils": CosmoUtils,
    }

    # Add all registered plugin utility types to the namespace
    plugin_service = PLUGIN_SERVICE.get()
    for util_type in plugin_service._utils.keys():
        namespace[util_type.__name__] = util_type

    return namespace


def _validate_no_imports(code: str) -> None:
    """Validate that code contains no import statements.

    Args:
        code: Python code string to validate

    Raises:
        ValueError: If import statements are found
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Invalid Python syntax: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            raise ValueError("Import statements are not allowed in rule code")


def _validate_only_functions(namespace_before: dict, namespace_after: dict) -> None:
    """Validate that only functions were added to the namespace.

    Args:
        namespace_before: Namespace before code execution
        namespace_after: Namespace after code execution

    Raises:
        ValueError: If non-function objects were added
    """
    added_items = set(namespace_after.keys()) - set(namespace_before.keys())

    for item_name in added_items:
        item = namespace_after[item_name]
        if not callable(item):
            raise ValueError(
                f"Only function definitions are allowed at top level, "
                f"found: {item_name} = {type(item).__name__}"
            )


def _validate_function_parameters(func: Callable, function_name: str) -> None:
    """Validate function parameters against RuleManager requirements.

    Args:
        func: Function to validate
        function_name: Name of the function for error messages

    Raises:
        ValueError: If function parameters don't meet requirements
    """
    from main import PLUGIN_SERVICE

    signature = inspect.signature(func)
    type_hints = get_type_hints(func)
    seen_types: set[type] = set()

    for param_name, param in signature.parameters.items():
        # Arguments must be positional with type hints and no defaults
        if param.kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.VAR_KEYWORD):
            raise ValueError(
                f"Function '{function_name}': Keyword-only parameter "
                f"'{param_name}' is not allowed"
            )
        if param.default != inspect.Parameter.empty:
            raise ValueError(
                f"Function '{function_name}': Default value for parameter "
                f"'{param_name}' is not allowed"
            )
        if param.annotation == inspect.Parameter.empty:
            raise ValueError(
                f"Function '{function_name}': Type hint for parameter "
                f"'{param_name}' is missing"
            )

        # Get the type hint
        type_hint = type_hints.get(param_name)
        if type_hint is None:
            raise ValueError(
                f"Function '{function_name}': Type hint for parameter "
                f"'{param_name}' is missing"
            )
        if not inspect.isclass(type_hint):
            raise ValueError(
                f"Function '{function_name}': Type hint for parameter "
                f"'{param_name}' must be a class"
            )

        # A utility may only be declared once
        if type_hint in seen_types:
            raise ValueError(
                f"Function '{function_name}': Utility type "
                f"{type_hint.__name__} is already declared"
            )
        seen_types.add(type_hint)

        # Validate plugin availability
        if type_hint == CosmoUtils:
            # CosmoUtils is always available
            continue
        else:
            plugin_service = PLUGIN_SERVICE.get()
            utility = plugin_service.util_for_type(type_hint)
            if utility is None:
                raise ValueError(
                    f"Function '{function_name}': No utility registered for type "
                    f"'{type_hint.__name__}' - is the plugin loaded?"
                )


def _extract_return_type_annotation(code: str, function_name: str) -> str | None:
    """Extract the return type annotation from a function definition.

    Args:
        code: Python code string containing function definition
        function_name: Name of the function to analyze

    Returns:
        String representation of return type annotation, or None if not found
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == function_name
            and node.returns is not None
        ):
            return ast.unparse(node.returns)

    return None


def compile_action_function(code: str) -> RuleRoutine:
    """Compile action code string into a RuleRoutine callable.

    Args:
        code: Python code string that defines an async function named "action"

    Returns:
        A callable that matches the RuleRoutine signature

    Raises:
        ValueError: If code is invalid, insecure, or function doesn't meet requirements
    """
    # Validate no imports
    _validate_no_imports(code)

    # Create safe execution namespace
    namespace = _get_safe_namespace()
    namespace_before = dict(namespace)

    # Execute the code
    try:
        exec(code, namespace)
    except Exception as e:
        raise ValueError(f"Failed to execute action code: {e}") from e

    # Validate only functions were added
    _validate_only_functions(namespace_before, namespace)

    # Extract the action function
    if "action" not in namespace:
        raise ValueError("Action code must define a function named 'action'")

    action_func = namespace["action"]
    if not callable(action_func):
        raise ValueError("'action' must be a callable function")

    # Validate it's async
    if not inspect.iscoroutinefunction(action_func):
        raise ValueError("Action function must be async (use 'async def action')")

    # Validate parameters
    _validate_function_parameters(action_func, "action")

    return cast(RuleRoutine, action_func)


def compile_trigger_function(code: str) -> RuleTriggerProvider:
    """Compile trigger code string into a RuleTriggerProvider callable.

    Args:
        code: Python code string that defines a function named "trigger"
              returning an AbstractCondition

    Returns:
        A callable that matches the RuleTriggerProvider signature

    Raises:
        ValueError: If code is invalid, insecure, or function doesn't meet requirements
    """
    # Validate no imports
    _validate_no_imports(code)

    # Create safe execution namespace
    namespace = _get_safe_namespace()
    namespace_before = dict(namespace)

    # Execute the code
    try:
        exec(code, namespace)
    except Exception as e:
        raise ValueError(f"Failed to execute trigger code: {e}") from e

    # Validate only functions were added
    _validate_only_functions(namespace_before, namespace)

    # Extract the trigger function
    if "trigger" not in namespace:
        raise ValueError("Trigger code must define a function named 'trigger'")

    trigger_func = namespace["trigger"]
    if not callable(trigger_func):
        raise ValueError("'trigger' must be a callable function")

    # Validate return type annotation
    return_type = _extract_return_type_annotation(code, "trigger")
    if return_type != "AbstractCondition":
        raise ValueError(
            f"Trigger function must have return type annotation "
            f"'-> AbstractCondition', found: {return_type}"
        )

    # Validate parameters
    _validate_function_parameters(trigger_func, "trigger")

    return cast(RuleTriggerProvider, trigger_func)


def compile_time_provider(code: str) -> RuleTimeProvider:
    """Compile time provider code string into a RuleTimeProvider callable.

    Args:
        code: Python code string that defines a function named "trigger"
              returning datetime | None

    Returns:
        A callable that matches the RuleTimeProvider signature

    Raises:
        ValueError: If code is invalid, insecure, or function doesn't meet requirements
    """
    # Validate no imports
    _validate_no_imports(code)

    # Create safe execution namespace
    namespace = _get_safe_namespace()
    namespace_before = dict(namespace)

    # Execute the code
    try:
        exec(code, namespace)
    except Exception as e:
        raise ValueError(f"Failed to execute time provider code: {e}") from e

    # Validate only functions were added
    _validate_only_functions(namespace_before, namespace)

    # Extract the trigger function (for time providers, it's still named "trigger")
    if "trigger" not in namespace:
        raise ValueError("Time provider code must define a function named 'trigger'")

    time_func = namespace["trigger"]
    if not callable(time_func):
        raise ValueError("'trigger' must be a callable function")

    # Validate return type annotation
    return_type = _extract_return_type_annotation(code, "trigger")
    if return_type not in ["datetime | None", "datetime|None", "Optional[datetime]"]:
        raise ValueError(
            f"Time provider function must have return type annotation "
            f"'-> datetime | None', found: {return_type}"
        )

    # Validate parameters
    _validate_function_parameters(time_func, "trigger")

    return cast(RuleTimeProvider, time_func)


def detect_rule_type(trigger_code: str) -> str:
    """Detect if trigger code defines a trigger-based or timer-based rule.

    Args:
        trigger_code: Python code string containing trigger logic

    Returns:
        Either "trigger" for event-based rules or "timer" for time-based rules

    Raises:
        ValueError: If rule type cannot be determined
    """
    # Extract return type annotation
    return_type = _extract_return_type_annotation(trigger_code, "trigger")

    if return_type is None:
        raise ValueError(
            "Cannot detect rule type: function 'trigger' must have a "
            "return type annotation"
        )

    # Normalize return type annotation
    normalized = return_type.replace(" ", "").lower()

    # Check for AbstractCondition (trigger rule)
    if "abstractcondition" in normalized:
        return "trigger"

    # Check for datetime | None (timer rule)
    if (
        "datetime|none" in normalized
        or "datetime" in normalized
        and "none" in normalized
        or "optional[datetime]" in normalized.replace(" ", "")
    ):
        return "timer"

    # If we can't determine the type, provide a helpful error
    raise ValueError(
        f"Cannot detect rule type from return annotation '{return_type}'. "
        f"Expected '-> AbstractCondition' for trigger rules or "
        f"'-> datetime | None' for timer rules"
    )
