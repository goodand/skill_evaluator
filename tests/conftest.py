"""pytest 설정 - scripts/ 디렉토리를 sys.path에 추가 + marker 등록."""

import os
import sys
from pathlib import Path

import pytest

# scripts/ 디렉토리를 import 경로에 추가
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# tests/ 디렉토리도 import 경로에 추가 (helpers.py 사용)
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


def pytest_configure(config):
    """커스텀 마커 등록."""
    config.addinivalue_line("markers", "integration: 실제 스킬 디렉토리 필요한 통합 테스트")


def pytest_collection_modifyitems(config, items):
    """SKILLS_ROOT가 없으면 integration 테스트를 skip."""
    root = os.environ.get("SKILLS_ROOT", "")
    has_root = bool(root) and Path(root).is_dir()
    if has_root:
        return

    skip_integration = pytest.mark.skip(reason="integration tests require SKILLS_ROOT=<valid skills dir>")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
