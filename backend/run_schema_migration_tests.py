#!/usr/bin/env python3
"""
Standalone test runner for KG Schema Migration Service tests.

Run with: python run_schema_migration_tests.py
"""

import sys
import os
from unittest.mock import MagicMock


def create_mock_module(name):
    """Create a mock module."""
    mock = MagicMock()
    mock.__name__ = name
    mock.__file__ = f"<mocked {name}>"
    return mock


# Mock external dependencies that may not be installed
mock_modules = [
    "sentence_transformers",
    "neo4j",
    "redis",
    "kafka",
]

for mod_name in mock_modules:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = create_mock_module(mod_name)

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


if __name__ == "__main__":
    import pytest

    print("=" * 60)
    print("KG Schema Migration Service Tests")
    print("=" * 60)

    test_file = os.path.join(project_root, "tests", "test_kg_schema_migration_service.py")
    exit_code = pytest.main([test_file, "-v", "--tb=short", "-p", "no:cov", "--override-ini=addopts="])
    sys.exit(exit_code)
