from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_kg_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "generate_codebase_kg.py"
    spec = importlib.util.spec_from_file_location("generate_codebase_kg", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_routes_extracts_metadata(tmp_path: Path):
    content = """\
from fastapi import APIRouter

router = APIRouter(prefix=\"/api/v1/health\")

@router.get(
    \"\",
    response_model=HealthResponse,
    tags=[\"Health\"],
    summary=\"Comprehensive health check\",
    description=\"Checks all dependencies\",
)
async def health_check():
    return {}

@router.post(\"/cache/clear\", status_code=204)
def clear_cache():
    return {}
"""
    file_path = tmp_path / "health.py"
    file_path.write_text(content, encoding="utf-8")

    kg = _load_kg_module()
    routes = kg.parse_routes(str(file_path))

    assert any(
        r.get("method") == "GET" and r.get("path") == "" for r in routes
    ), "Expected root path GET route"
    assert any(
        r.get("method") == "POST" and r.get("path") == "/cache/clear" for r in routes
    ), "Expected POST /cache/clear route"

    get_route = next(r for r in routes if r.get("method") == "GET")
    assert get_route.get("response_model") == "HealthResponse"
    assert get_route.get("tags") == ["Health"]
    assert get_route.get("summary") == "Comprehensive health check"
    assert get_route.get("description") == "Checks all dependencies"
