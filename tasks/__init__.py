"""
hartes.tasks — Task registry and base abstractions.

A Task is the first-class unit of work in Hartes.
Every autonomous flywheel cycle operates on a Task instance.
"""

from tasks.base import Task, TaskResult, TaskStatus
from tasks.registry import TaskRegistry

__all__ = ["Task", "TaskResult", "TaskStatus", "TaskRegistry"]
