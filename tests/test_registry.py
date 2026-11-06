import pytest
from unittest.mock import patch
from tasks.registry import TaskRegistry

def test_list_available():
    mock_registry = {
        'task_c': None,
        'task_a': None,
        'task_b': None,
    }

    with patch.object(TaskRegistry, '_discover'):
        with patch.dict(TaskRegistry._available_tasks, mock_registry, clear=True):
            available = TaskRegistry.list_available()
            assert available == ['task_a', 'task_b', 'task_c']
