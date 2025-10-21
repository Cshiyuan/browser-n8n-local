"""Utilities for handling JSON schema and dynamic Pydantic models"""

import json
from enum import Enum
from typing import Any, Optional, get_args, get_origin

from pydantic import BaseModel, Field, create_model

from task.constants import logger


def _create_enum_from_schema(field_name: str, enum_values: list) -> type[Enum]:
    """Create an Enum class from a list of values"""
    # Create enum members dict
    enum_members = {str(val).upper().replace('-', '_').replace(' ', '_'): val for val in enum_values}
    # Create and return the Enum class
    return Enum(f"{field_name.capitalize()}Enum", enum_members)


def _parse_field_schema(
    field_name: str,
    field_schema: dict,
    is_required: bool,
    model_name_prefix: str = ""
) -> tuple[type, Any]:
    """Parse a single field schema and return (type, default) tuple for create_model()

    Args:
        field_name: Name of the field
        field_schema: JSON schema for this field
        is_required: Whether this field is required
        model_name_prefix: Prefix for nested model names

    Returns:
        Tuple of (python_type, field_default) suitable for create_model()
    """
    # Type mapping from JSON Schema to Python types
    TYPE_MAP = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "null": type(None),
    }

    json_type = field_schema.get("type", "string")
    description = field_schema.get("description")
    default_value = field_schema.get("default")
    enum_values = field_schema.get("enum")

    # Handle enum types
    if enum_values:
        python_type = _create_enum_from_schema(field_name, enum_values)
    # Handle nested object types - create a nested Pydantic model
    elif json_type == "object":
        nested_properties = field_schema.get("properties", {})
        if nested_properties:
            nested_model_name = f"{model_name_prefix}{field_name.replace('_', ' ').title().replace(' ', '')}"
            python_type = _parse_schema_to_model(field_schema, nested_model_name, model_name_prefix)
        else:
            # No properties defined - use dict but warn
            logger.warning(
                f"Field '{field_name}' is type 'object' but has no 'properties'. "
                f"Using dict type. This may cause issues with strict API validators."
            )
            python_type = dict
    # Handle array types
    elif json_type == "array":
        items_schema = field_schema.get("items", {})
        if items_schema.get("type") == "object" and items_schema.get("properties"):
            # Array of objects - create nested model for items
            nested_model_name = f"{model_name_prefix}{field_name.replace('_', ' ').title().replace(' ', '')}Item"
            item_type = _parse_schema_to_model(items_schema, nested_model_name, model_name_prefix)
            python_type = list[item_type]
        else:
            # Simple array or array with enum items
            item_type_str = items_schema.get("type", "string")
            if items_schema.get("enum"):
                item_type = _create_enum_from_schema(f"{field_name}_item", items_schema["enum"])
            else:
                item_type = TYPE_MAP.get(item_type_str, Any)
            python_type = list[item_type] if item_type != Any else list
    # Simple types
    else:
        python_type = TYPE_MAP.get(json_type, Any)

    # Build the field specification
    if is_required:
        if description:
            return (python_type, Field(..., description=description))
        else:
            return (python_type, ...)
    else:
        if description:
            return (Optional[python_type], Field(default=default_value, description=description))
        else:
            return (Optional[python_type], default_value)


def _parse_schema_to_model(
    schema_dict: dict,
    model_name: str = "DynamicModel",
    model_name_prefix: str = ""
) -> type[BaseModel]:
    """Recursively parse JSON schema dict and create nested Pydantic models

    This helper function handles nested objects by creating separate Pydantic models
    for each nested object type, ensuring proper schema generation for strict
    validators like Google Gemini API.

    Args:
        schema_dict: JSON schema dictionary
        model_name: Name for the generated model
        model_name_prefix: Prefix for nested model names

    Returns:
        Pydantic BaseModel class
    """
    properties = schema_dict.get("properties", {})
    required_fields = set(schema_dict.get("required", []))

    if not properties:
        logger.warning(f"Schema '{model_name}' has no properties, creating empty model")
        return create_model(model_name)

    # Build field definitions
    field_definitions = {}

    for field_name, field_schema in properties.items():
        is_required = field_name in required_fields
        field_definitions[field_name] = _parse_field_schema(
            field_name,
            field_schema,
            is_required,
            f"{model_name}_"
        )

    # Create the Pydantic model
    return create_model(model_name, **field_definitions)


def parse_output_model_schema(schema_str: str) -> Optional[type[BaseModel]]:
    """Parse JSON schema string and create a dynamic Pydantic model

    This function recursively processes JSON Schema and creates proper nested Pydantic
    models (not plain dicts) for object types. This ensures compatibility with strict
    API validators like Google Gemini that reject empty object properties.

    Features:
    - Nested objects → Nested Pydantic models (not dict)
    - Enums → Python Enum classes
    - Arrays with object items → list[NestedModel]
    - Proper handling of required/optional fields
    - Field descriptions preserved

    Args:
        schema_str: JSON schema as string conforming to JSON Schema specification

    Returns:
        Dynamically created Pydantic BaseModel class, or None if parsing fails

    Example:
        >>> schema = '''
        ... {
        ...     "title": "LoginCheckResult",
        ...     "type": "object",
        ...     "properties": {
        ...         "data": {
        ...             "type": "object",
        ...             "properties": {
        ...                 "result": {"type": "string", "enum": ["LOGGED_IN", "LOGGED_OUT"]}
        ...             }
        ...         },
        ...         "type": {"type": "string"},
        ...         "msg": {"type": "string"}
        ...     },
        ...     "required": ["data", "type", "msg"]
        ... }
        ... '''
        >>> Model = parse_output_model_schema(schema)
        >>> instance = Model(data={"result": "LOGGED_IN"}, type="check", msg="OK")
    """
    try:
        # Parse JSON schema
        schema = json.loads(schema_str)

        if not isinstance(schema, dict) or schema.get("type") != "object":
            logger.error("Schema must be a JSON object with type='object'")
            return None

        # Extract model name
        model_name = schema.get("title", "DynamicOutputModel")

        # Use the recursive helper to create the model
        dynamic_model = _parse_schema_to_model(schema, model_name)

        logger.info(
            f"Created Pydantic model '{model_name}' with nested object support using create_model()"
        )

        return dynamic_model

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schema string: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating Pydantic model from JSON schema: {e}")
        logger.exception("Full traceback:")
        return None