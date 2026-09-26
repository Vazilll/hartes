"""
hartes.tasks.registry — Task discovery and instantiation.

TaskRegistry scans `tasks/builtin/` for Task subclasses and exposes
a simple `load(name, **kwargs)` interface for the CLI runner.

Usage:
    registry = TaskRegistry()
    task = registry.load("code_optimizer", input_file="my_script.py")
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Dict, Type

from tasks.base import Task


class TaskRegistry:
    """
    Auto-discovers Task subclasses from `tasks/builtin/`.

    Registration is implicit: any module in `tasks/builtin/` that defines
    a class inheriting from Task is automatically registered under its
    module name (e.g., `code_optimizer` for `tasks/builtin/code_optimizer.py`).
    """

    _registry: Dict[str, Type[Task]] = {}
    _discovered: bool = False

    @classmethod
    def _discover(cls) -> None:
        if cls._discovered:
            return
        builtin_pkg = "tasks.builtin"
        builtin_path = Path(__file__).parent / "builtin"
        if not builtin_path.exists():
            cls._discovered = True
            return
        for _, module_name, _ in pkgutil.iter_modules([str(builtin_path)]):
            full_name = f"{builtin_pkg}.{module_name}"
            try:
                mod = importlib.import_module(full_name)
            except Exception:
                continue
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, Task) and obj is not Task and not inspect.isabstract(obj):
                    cls._registry[module_name] = obj
        cls._discovered = True

    @classmethod
    def load(cls, name: str, **kwargs) -> Task:
        """
        Load and instantiate a Task by name.

        Args:
            name:    Short name matching the builtin module filename, e.g. "code_optimizer".
            **kwargs: Forwarded to the Task subclass constructor.

        Returns:
            An instantiated Task ready to run.

        Raises:
            KeyError: If no task with the given name is found.
        """
        cls._discover()
        if name not in cls._registry:
            available = ", ".join(sorted(cls._registry.keys()))
            raise KeyError(
                f"No task named '{name}'. Available: [{available}]"
            )
        task_cls = cls._registry[name]
        return task_cls(**kwargs)

    @classmethod
    def list_available(cls) -> list[str]:
        """Return names of all discovered tasks."""
        cls._discover()
        return sorted(cls._registry.keys())
