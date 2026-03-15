"""BlenderBot MCP Tools - Modular tool packages for Blender operations."""

from .base import ToolsPackageBase
from .object_tools import ObjectTools
from .material_tools import MaterialTools
from .scene_tools import SceneTools
from .modifier_tools import ModifierTools
from .polyhaven_tools import PolyhavenTools


def get_all_tool_definitions() -> list[dict]:
    """Get all tool definitions formatted for Claude's tool_use API."""
    tools = []
    for package_cls in ToolsPackageBase.get_all_packages():
        tools.extend(package_cls.get_tool_definitions())
    return tools


def get_tool_executor(tool_name: str):
    """Look up a tool function by name across all packages."""
    for package_cls in ToolsPackageBase.get_all_packages():
        func = package_cls.get_tool(tool_name)
        if func:
            return func
    return None
