"""Run labeled RCA scenarios against a live cluster, then score with hard rules.

  python -m agent_cli.eval_rca --list
  python -m agent_cli.eval_rca --dry-run
  python -m agent_cli.eval_rca --scenario healthy-baseline
  python -m agent_cli.eval_rca --all

Needs: cluster + citrus namespace + Chaos Mesh (for kill scenarios) + DEEPSEEK_API_KEY.
Does not need Chaos Mesh for healthy-baseline.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .agent import ReActAgent
from .config import AgentConfig
from .eval_scenarios import SCENARIOS, Scenario, scenario_by_id
from .eval_score import Score, score


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_OUT = _REPO_ROOT / "data" / "eval"


def _kubectl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _inject(scenario: Scenario) -> None:
    path = scenario.manifest_path()
    if path is None:
        return
    if not path.exists():
        raise FileNotFoundError(f"chaos manifest missing: {path}")
    delete = _kubectl("delete", "-f", str(path), "--ignore-not-found")
    if delete.returncode != 0:
        raise RuntimeError(delete.stderr or delete.stdout)
    time.sleep(2)
    apply = _kubectl("apply", "-f", str(path))
    if apply.returncode != 0:
        raise RuntimeError(apply.stderr or apply.stdout)
    print(f"  injected {path.name}, waiting {scenario.wait_seconds}s...")
    time.sleep(scenario.wait_seconds)


def _cleanup(scenario: Scenario) -> None:
    path = scenario.manifest_path()
    if path is None:
        return
    _kubectl("delete", "-f", str(path), "--ignore-not-found")


def _print_score(result: Score) -> None:
    mark = "HIT " if result.root_cause_hit else "MISS"
    print(f"  {mark}  evidence={result.evidence_level}  "
          f"{result.duration_s}s  steps={result.steps}  tools={result.tool_calls}")
    if result.missing_required:
        print(f"    missing required: {result.missing_required}")
    if result.missing_any:
        print(f"    needed one of: {result.missing_any}")
    if result.forbidden_hits:
        print(f"    forbidden phrases: {result.forbidden_hits}")
    if result.expected_tools_missing:
        print(f"    expected tools not called: {result.expected_tools_missing}")


def _print_table(results: List[Score]) -> None:
    hits = sum(1 for r in results if r.root_cause_hit)
    print("\n" + "=" * 72)
    print(f"{'scenario':<24} {'hit':<6} {'evidence':<8} {'sec':<8} {'tools'}")
    print("-" * 72)
    for r in results:
        print(f"{r.scenario_id:<24} {str(r.root_cause_hit):<6} "
              f"{r.evidence_level:<8} {str(r.duration_s):<8} {r.tool_calls}")
    print("-" * 72)
    print(f"root-cause hit rate: {hits}/{len(results)}")
    print("=" * 72)


def _save(out_dir: Path, results: List[Score]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"rca_eval_{stamp}.json"
    payload = {
        "created_utc": stamp,
        "hit_rate": (
            sum(1 for r in results if r.root_cause_hit) / len(results)
            if results else 0.0
        ),
        "results": [r.as_dict() for r in results],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {path}")
    return path


async def _run_scenarios(
    scenarios: Iterable[Scenario],
    *,
    skip_inject: bool,
    no_cleanup: bool,
    out_dir: Path,
) -> List[Score]:
    config = AgentConfig()
    if not config.api_key:
        print("Error: DEEPSEEK_API_KEY is not set")
        sys.exit(1)

    agent = ReActAgent(config)
    await agent.initialize()
    results: List[Score] = []
    try:
        for scenario in scenarios:
            print(f"\n=== {scenario.id} ===")
            print(f"  {scenario.notes}")
            try:
                if not skip_inject:
                    _inject(scenario)
                answer = await agent.run(scenario.query)
                result = score(scenario, answer, agent.stats)
                results.append(result)
                _print_score(result)
            except Exception as exc:
                print(f"  ERROR: {exc}")
                results.append(Score(
                    scenario_id=scenario.id,
                    root_cause_hit=False,
                    answer_body=f"ERROR: {exc}",
                    evidence_level="LOW",
                    evidence_reasons=[str(exc)],
                ))
            finally:
                if not skip_inject and not no_cleanup:
                    _cleanup(scenario)
    finally:
        await agent.cleanup()

    _print_table(results)
    _save(out_dir, results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Labeled RCA eval (hard-rule scorer)")
    parser.add_argument("--list", action="store_true", help="Print the catalog and exit")
    parser.add_argument("--dry-run", action="store_true", help="Show inject plan, do not call the LLM")
    parser.add_argument("--scenario", help="Run one scenario id")
    parser.add_argument("--all", action="store_true", help="Run every scenario in catalog order")
    parser.add_argument("--skip-inject", action="store_true", help="Do not apply/delete Chaos Mesh")
    parser.add_argument("--no-cleanup", action="store_true", help="Leave the Chaos CR in the cluster")
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    if args.list or args.dry_run:
        for s in SCENARIOS:
            inj = s.manifest or "(no inject)"
            print(f"{s.id:<24} wait={s.wait_seconds:<4} {inj}")
            print(f"  query: {s.query}")
            print(f"  {s.notes}")
        if args.dry_run:
            print("\nCatalog order is the run order. healthy-baseline is first on purpose.")
        return

    if args.scenario:
        chosen = [scenario_by_id(args.scenario)]
    elif args.all:
        chosen = list(SCENARIOS)
    else:
        parser.print_help()
        sys.exit(1)

    asyncio.run(_run_scenarios(
        chosen,
        skip_inject=args.skip_inject,
        no_cleanup=args.no_cleanup,
        out_dir=args.out_dir,
    ))


if __name__ == "__main__":
    main()
