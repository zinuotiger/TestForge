
import sys
from unittest.mock import MagicMock

import pytest

@pytest.fixture
def sample_python_code():
    """Provide sample Python code with basic arithmetic functions."""
    return '''
def add(a, b):
    """Addition function"""
    return a + b

def subtract(a, b):
    """Subtraction function"""
    return a - b

def multiply(a, b):
    """Multiplication function"""
    return a * b

def divide(a, b):
    """Division function"""
    if b == 0:
        raise ValueError("\u9664\u6570\u4e0d\u80fd\u4e3a0")
    return a / b
'''

def pytest_configure(config):
    config.addinivalue_line("markers", "agent: mark test as agent-related test")
    config.addinivalue_line("markers", "asyncio: mark test as async test")

class _MockModule:
    def __init__(self, name):
        self._name = name
        self._mock = MagicMock()
        # Make it callable
    def __getattr__(self, name):
        return MagicMock()
    def __call__(self, *args, **kwargs):
        return MagicMock()(*args, **kwargs)

_MISSING_MODULES = [
    # 'backend.analyzer',  # now real module with languages
    'backend.dsl',
    'backend.reporter',
    'backend.testing',
    'backend.testing.models',
    'backend.quality.mutation',
    'backend.generator.template_generator',
    'backend.analysis.static_analyzer',
]

# Pre-register all mocks BEFORE any imports happen
for name in _MISSING_MODULES:
    if name not in sys.modules:
        sys.modules[name] = _MockModule(name)
