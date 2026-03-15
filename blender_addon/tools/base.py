"""Base class for modular tool packages.

Each tool package groups related Blender operations (e.g., object manipulation,
materials, modifiers). Tools are exposed as structured functions that can be
called by the LLM via Claude's tool_use API.
"""

import inspect
import typing
from typing import get_type_hints


class ToolsPackageBase:
    """Base class for tool packages. Subclasses define tools as static methods."""

    _exclude = {"get_all_packages", "get_tool_definitions", "get_tool", "get_all_tools"}

    @classmethod
    def get_all_packages(cls) -> list[type]:
        """Return all registered tool package subclasses."""
        return cls.__subclasses__()

    @classmethod
    def get_all_tools(cls) -> list[tuple[str, callable]]:
        """Return all tool functions in this package as (name, func) pairs."""
        tools = []
        for name in cls.__dict__:
            if name.startswith("_") or name in cls._exclude:
                continue
            func = getattr(cls, name)
            if callable(func):
                tools.append((name, func))
        return tools

    @classmethod
    def get_tool(cls, tool_name: str):
        """Look up a specific tool by name."""
        for name, func in cls.get_all_tools():
            if name == tool_name:
                return func
        return None

    @classmethod
    def get_tool_definitions(cls) -> list[dict]:
        """Generate Claude tool_use definitions from this package's methods."""
        definitions = []
        for name, func in cls.get_all_tools():
            definition = _func_to_tool_definition(name, func)
            if definition:
                definitions.append(definition)
        return definitions


def _python_type_to_json_schema(annotation) -> dict:
    """Convert a Python type annotation to a JSON Schema type."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return {"type": "string"}

    origin = getattr(annotation, "__origin__", None)

    if annotation is str:
        return {"type": "string"}
    elif annotation is int:
        return {"type": "integer"}
    elif annotation is float:
        return {"type": "number"}
    elif annotation is bool:
        return {"type": "boolean"}
    elif origin is list or annotation is list:
        args = getattr(annotation, "__args__", None)
        if args:
            return {"type": "array", "items": _python_type_to_json_schema(args[0])}
        return {"type": "array"}
    elif origin is dict or annotation is dict:
        return {"type": "object"}
    else:
        return {"type": "string"}


def _func_to_tool_definition(name: str, func: callable) -> dict | None:
    """Convert a Python function to a Claude tool_use definition."""
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""

    # Parse description and parameter docs from docstring
    description_lines = []
    param_docs = {}
    in_args = False
    for line in doc.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if stripped.lower().startswith("returns:"):
            in_args = False
            continue
        if in_args and stripped.startswith("- "):
            # Parse "- param_name: description"
            parts = stripped[2:].split(":", 1)
            if len(parts) == 2:
                param_docs[parts[0].strip()] = parts[1].strip()
        elif not in_args:
            description_lines.append(stripped)

    description = " ".join(description_lines).strip()

    # Build properties from function signature
    properties = {}
    required = []
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        annotation = hints.get(param_name, param.annotation)
        prop = _python_type_to_json_schema(annotation)

        if param_name in param_docs:
            prop["description"] = param_docs[param_name]

        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            if param.default is not None:
                prop["default"] = param.default

        properties[param_name] = prop

    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }
