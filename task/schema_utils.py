"""Utilities for handling JSON schema and dynamic Pydantic models"""

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, create_model

from task.constants import logger


def parse_output_model_schema(schema_str: str) -> Optional[type[BaseModel]]:
    """Parse JSON schema string and create a dynamic Pydantic model using official Pydantic API

    This function uses Pydantic's create_model() which is the official way to
    dynamically create Pydantic models at runtime.

    Args:
        schema_str: JSON schema as string conforming to JSON Schema specification

    Returns:
        Dynamically created Pydantic BaseModel class, or None if parsing fails

    Example:
        >>> schema = '''
        ... {
        ...     "title": "SearchResult",
        ...     "type": "object",
        ...     "properties": {
        ...         "query": {"type": "string", "description": "Search query"},
        ...         "count": {"type": "integer", "description": "Result count"}
        ...     },
        ...     "required": ["query"]
        ... }
        ... '''
        >>> Model = parse_output_model_schema(schema)
        >>> instance = Model(query="test", count=5)
    """
    try:
        # Parse JSON schema
        schema = json.loads(schema_str)

        if not isinstance(schema, dict) or schema.get("type") != "object":
            logger.error("Schema must be a JSON object with type='object'")
            return None

        # Extract model information
        model_name = schema.get("title", "DynamicOutputModel")
        properties = schema.get("properties", {})
        required_fields = set(schema.get("required", []))

        if not properties:
            logger.warning("Schema has no properties, creating empty model")
            return create_model(model_name)

        # Type mapping from JSON Schema to Python types
        TYPE_MAP = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        # Build field definitions for Pydantic's create_model()
        field_definitions = {}

        for field_name, field_schema in properties.items():
            json_type = field_schema.get("type", "string")
            python_type = TYPE_MAP.get(json_type, Any)
            description = field_schema.get("description")
            default_value = field_schema.get("default")
            is_required = field_name in required_fields

            # Use Pydantic's Field for metadata
            if is_required:
                # Required field: use ... (Ellipsis) as marker
                field_definitions[field_name] = (
                    python_type,
                    Field(..., description=description) if description else ...
                )
            else:
                # Optional field with default
                field_definitions[field_name] = (
                    Optional[python_type],
                    Field(default=default_value, description=description)
                    if description else default_value
                )

        # Use Pydantic's official create_model() function
        DynamicModel = create_model(model_name, **field_definitions)

        logger.info(
            f"Created Pydantic model '{model_name}' with {len(field_definitions)} fields "
            f"using create_model()"
        )

        return DynamicModel

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schema string: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating Pydantic model from JSON schema: {e}")
        return None