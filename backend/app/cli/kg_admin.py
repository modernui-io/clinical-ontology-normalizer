"""CLI tools for Knowledge Graph administration.

This module provides command-line utilities for managing the knowledge graph:
- Health checks and diagnostics
- Cache management
- Benchmark execution
- Data import/export
- Statistics and reporting

Usage:
    python -m app.cli.kg_admin health
    python -m app.cli.kg_admin cache --stats
    python -m app.cli.kg_admin benchmark --suite medagentbench
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any


def get_health_status() -> dict[str, Any]:
    """Get health status of all KG components."""
    try:
        from app.services.graph_database_service import get_graph_database_service
        from app.services.graph_analytics_service import get_graph_analytics_service
        from app.services.graph_embedding_service import get_graph_embedding_service
        from app.services.causal_reasoning_service import get_causal_reasoning_service
        from app.services.provenance_service import get_provenance_service
        from app.services.multi_agent_orchestrator import get_multi_agent_orchestrator
        from app.services.kg_visualization_service import get_kg_visualization_service
        from app.services.medagentbench_service import get_medagentbench_service
        from app.services.drknows_benchmark_service import get_drknows_benchmark_service
        from app.services.kg_partitioning_service import get_kg_partitioning_service
        from app.services.kg_kafka_streaming_service import get_kg_kafka_streaming_service
    except ImportError as e:
        return {"error": f"Failed to import services: {e}"}

    now = datetime.now(timezone.utc)
    components = []

    # Check each service
    services_to_check = [
        ("graph_database", get_graph_database_service),
        ("graph_analytics", get_graph_analytics_service),
        ("graph_embedding", get_graph_embedding_service),
        ("causal_reasoning", get_causal_reasoning_service),
        ("provenance", get_provenance_service),
        ("multi_agent_orchestrator", get_multi_agent_orchestrator),
        ("kg_visualization", get_kg_visualization_service),
        ("medagentbench", get_medagentbench_service),
        ("drknows_benchmark", get_drknows_benchmark_service),
        ("kg_partitioning", get_kg_partitioning_service),
        ("kg_kafka_streaming", get_kg_kafka_streaming_service),
    ]

    for name, getter in services_to_check:
        try:
            svc = getter()
            stats = {}
            if hasattr(svc, "get_stats"):
                stats = svc.get_stats()
            elif hasattr(svc, "get_metrics"):
                stats = svc.get_metrics()
            components.append({
                "name": name,
                "status": "healthy",
                "timestamp": now.isoformat(),
                "details": stats if isinstance(stats, dict) else {"loaded": True},
            })
        except Exception as e:
            components.append({
                "name": name,
                "status": "unhealthy",
                "timestamp": now.isoformat(),
                "error": str(e),
            })

    healthy = sum(1 for c in components if c["status"] == "healthy")
    overall = "healthy" if healthy == len(components) else (
        "degraded" if healthy > 0 else "unhealthy"
    )

    return {
        "overall_status": overall,
        "timestamp": now.isoformat(),
        "total_components": len(components),
        "healthy_components": healthy,
        "components": components,
    }


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    try:
        from app.services.kg_cache_service import get_kg_cache_service
        cache = get_kg_cache_service()
        stats = cache.get_stats()
        return stats.to_dict()
    except ImportError as e:
        return {"error": f"Cache service not available: {e}"}
    except Exception as e:
        return {"error": str(e)}


def clear_cache(cache_type: str | None = None) -> dict[str, Any]:
    """Clear cache entries."""
    try:
        from app.services.kg_cache_service import get_kg_cache_service, CacheType
        cache = get_kg_cache_service()

        if cache_type:
            try:
                ct = CacheType(cache_type)
                count = cache.invalidate_by_type(ct)
                return {"cleared": count, "cache_type": cache_type}
            except ValueError:
                return {"error": f"Invalid cache type: {cache_type}"}
        else:
            count = cache.clear()
            return {"cleared": count, "cache_type": "all"}
    except ImportError as e:
        return {"error": f"Cache service not available: {e}"}
    except Exception as e:
        return {"error": str(e)}


def get_tracing_stats() -> dict[str, Any]:
    """Get tracing statistics."""
    try:
        from app.services.kg_tracing_service import get_kg_tracing_service
        tracer = get_kg_tracing_service()
        metrics = tracer.get_metrics()
        return metrics.to_dict()
    except ImportError as e:
        return {"error": f"Tracing service not available: {e}"}
    except Exception as e:
        return {"error": str(e)}


def run_benchmark(suite_name: str, case_id: str | None = None) -> dict[str, Any]:
    """Run a benchmark suite or single case."""
    try:
        from app.services.medagentbench_service import get_medagentbench_service
        from app.services.drknows_benchmark_service import get_drknows_benchmark_service

        if suite_name.lower() in ["medagentbench", "medagent", "ma"]:
            svc = get_medagentbench_service()
            suites = svc.list_suites()
            if not suites:
                return {"error": "No benchmark suites available"}

            if case_id:
                # Run single case
                result = svc.run_benchmark(case_id)
                return result.to_dict() if hasattr(result, "to_dict") else {"result": str(result)}
            else:
                # Run all suites and return summary
                results = []
                for suite in suites[:3]:  # Limit to first 3 suites for CLI
                    result = svc.run_suite(suite)
                    results.append({
                        "suite": suite,
                        "passed": result.passed if hasattr(result, "passed") else None,
                        "total": result.total if hasattr(result, "total") else None,
                    })
                return {"benchmark": "medagentbench", "results": results}

        elif suite_name.lower() in ["drknows", "drk"]:
            svc = get_drknows_benchmark_service()
            baselines = svc.get_baselines()
            return {"benchmark": "drknows", "baselines": baselines}

        else:
            return {"error": f"Unknown benchmark suite: {suite_name}"}

    except ImportError as e:
        return {"error": f"Benchmark service not available: {e}"}
    except Exception as e:
        return {"error": str(e)}


def get_stats() -> dict[str, Any]:
    """Get overall KG statistics."""
    try:
        from app.services.graph_database_service import get_graph_database_service
        from app.services.kg_cache_service import get_kg_cache_service
        from app.services.kg_tracing_service import get_kg_tracing_service

        stats = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Graph database stats
        try:
            db = get_graph_database_service()
            db_stats = db.get_stats() if hasattr(db, "get_stats") else {}
            stats["graph_database"] = db_stats
        except Exception as e:
            stats["graph_database"] = {"error": str(e)}

        # Cache stats
        try:
            cache = get_kg_cache_service()
            cache_stats = cache.get_stats()
            stats["cache"] = cache_stats.to_dict()
        except Exception as e:
            stats["cache"] = {"error": str(e)}

        # Tracing stats
        try:
            tracer = get_kg_tracing_service()
            trace_metrics = tracer.get_metrics()
            stats["tracing"] = trace_metrics.to_dict()
        except Exception as e:
            stats["tracing"] = {"error": str(e)}

        return stats

    except Exception as e:
        return {"error": str(e)}


def print_json(data: dict[str, Any]) -> None:
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=2, default=str))


def cmd_health(args: argparse.Namespace) -> int:
    """Handle health command."""
    result = get_health_status()
    print_json(result)

    if result.get("overall_status") == "unhealthy":
        return 1
    return 0


def cmd_cache(args: argparse.Namespace) -> int:
    """Handle cache command."""
    if args.clear:
        result = clear_cache(args.type)
    else:
        result = get_cache_stats()

    print_json(result)
    return 0 if "error" not in result else 1


def cmd_tracing(args: argparse.Namespace) -> int:
    """Handle tracing command."""
    result = get_tracing_stats()
    print_json(result)
    return 0 if "error" not in result else 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Handle benchmark command."""
    result = run_benchmark(args.suite, args.case)
    print_json(result)
    return 0 if "error" not in result else 1


def cmd_stats(args: argparse.Namespace) -> int:
    """Handle stats command."""
    result = get_stats()
    print_json(result)
    return 0 if "error" not in result else 1


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="kg-admin",
        description="Knowledge Graph administration CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Health command
    health_parser = subparsers.add_parser("health", help="Check health of KG components")
    health_parser.set_defaults(func=cmd_health)

    # Cache command
    cache_parser = subparsers.add_parser("cache", help="Manage KG cache")
    cache_parser.add_argument("--clear", action="store_true", help="Clear cache")
    cache_parser.add_argument("--type", help="Cache type to clear (concept, path, etc.)")
    cache_parser.set_defaults(func=cmd_cache)

    # Tracing command
    tracing_parser = subparsers.add_parser("tracing", help="View tracing statistics")
    tracing_parser.set_defaults(func=cmd_tracing)

    # Benchmark command
    benchmark_parser = subparsers.add_parser("benchmark", help="Run benchmarks")
    benchmark_parser.add_argument("--suite", required=True, help="Benchmark suite (medagentbench, drknows)")
    benchmark_parser.add_argument("--case", help="Specific case ID to run")
    benchmark_parser.set_defaults(func=cmd_benchmark)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="View overall statistics")
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
