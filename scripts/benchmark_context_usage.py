#!/usr/bin/env python3
"""Benchmark old vs new multi-agent context policies.

This script compares two prompt sets against scenario definitions and estimates
input-token usage for each stage of the feature pipeline.

It is designed for proxy benchmarking when provider-billing telemetry is not
available locally. The primary metric is "stage input tokens", which counts
re-reads across planner, coder, tester, and reviewer because those stages run
as separate agent invocations.

Scenario files are JSON arrays shaped like:

[
  {
    "name": "localized fix",
    "kind": "Localized",
    "paths": {
      "changed": ["/abs/path/to/file.py"],
      "direct_dependencies": ["/abs/path/to/helper.py"],
      "pattern_files": ["/abs/path/to/existing_pattern.py"],
      "tests": ["/abs/path/to/test_file.py"],
      "config": ["/abs/path/to/pyproject.toml"],
      "nearby_context": ["/abs/path/to/neighbor.py"]
    }
  }
]

The old policy includes `nearby_context` broadly; the new policy excludes it
unless you classify that file as a direct dependency, pattern file, test, or
config relevant to the edited path.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Iterable


STAGES = ("planner", "coder", "tester", "reviewer")

OLD_POLICY = {
    "planner": ("changed", "direct_dependencies", "pattern_files", "tests", "config", "nearby_context"),
    "coder": ("changed", "direct_dependencies", "pattern_files", "tests", "nearby_context"),
    "tester": ("changed", "direct_dependencies", "tests", "config", "nearby_context"),
    "reviewer": ("changed", "direct_dependencies", "tests", "nearby_context"),
}

NEW_POLICY = {
    "planner": ("changed", "direct_dependencies", "pattern_files", "tests", "config"),
    "coder": ("changed", "direct_dependencies", "pattern_files", "tests"),
    "tester": ("changed", "direct_dependencies", "tests", "config"),
    "reviewer": ("changed", "direct_dependencies", "tests"),
}


@dataclass(frozen=True)
class PromptSet:
    planner: Path
    coder: Path
    tester: Path
    reviewer: Path

    def path_for(self, stage: str) -> Path:
        return getattr(self, stage)


def estimate_tokens(text: str) -> int:
    """Fallback estimate when no provider tokenizer is available locally."""
    return ceil(len(text) / 4)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def token_count_for_path(path: Path) -> int:
    return estimate_tokens(read_text(path))


def unique_paths_for_stage(path_groups: dict[str, list[str]], categories: Iterable[str]) -> list[Path]:
    ordered: list[Path] = []
    seen: set[Path] = set()
    for category in categories:
        for raw_path in path_groups.get(category, []):
            path = Path(raw_path).expanduser()
            if path not in seen:
                ordered.append(path)
                seen.add(path)
    return ordered


def sum_tokens(paths: Iterable[Path]) -> int:
    return sum(token_count_for_path(path) for path in paths)


def load_prompt_set(directory: Path) -> PromptSet:
    return PromptSet(
        planner=directory / "planner.md",
        coder=directory / "coder.md",
        tester=directory / "tester.md",
        reviewer=directory / "reviewer.md",
    )


def format_int(value: int) -> str:
    return f"{value:,}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-prompts", required=True, type=Path, help="Directory containing old agent prompts")
    parser.add_argument("--new-prompts", required=True, type=Path, help="Directory containing new agent prompts")
    parser.add_argument("--scenarios", required=True, type=Path, help="JSON file describing benchmark scenarios")
    args = parser.parse_args()

    old_prompts = load_prompt_set(args.old_prompts)
    new_prompts = load_prompt_set(args.new_prompts)
    scenarios = json.loads(read_text(args.scenarios))

    prompt_tokens = {
        "old": {stage: token_count_for_path(old_prompts.path_for(stage)) for stage in STAGES},
        "new": {stage: token_count_for_path(new_prompts.path_for(stage)) for stage in STAGES},
    }

    print("| Scenario | Type | Old reads | New reads | Old stage-input ~tokens | New stage-input ~tokens | Delta | Reduction |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")

    for scenario in scenarios:
        name = scenario["name"]
        kind = scenario.get("kind", "")
        path_groups = scenario["paths"]

        totals: dict[str, int] = {"old": 0, "new": 0}
        read_counts: dict[str, int] = {"old": 0, "new": 0}

        for label, policy in (("old", OLD_POLICY), ("new", NEW_POLICY)):
            for stage in STAGES:
                stage_paths = unique_paths_for_stage(path_groups, policy[stage])
                totals[label] += prompt_tokens[label][stage] + sum_tokens(stage_paths)
                read_counts[label] += len(stage_paths)

        delta = totals["new"] - totals["old"]
        reduction = ((totals["old"] - totals["new"]) / totals["old"]) * 100 if totals["old"] else 0.0

        print(
            "| "
            f"{name} | {kind} | {read_counts['old']} | {read_counts['new']} | "
            f"{format_int(totals['old'])} | {format_int(totals['new'])} | "
            f"{delta:+,} | {reduction:.1f}% |"
        )

    print()
    print("| Scenario | Old unique files | New unique files | Old unique-context ~tokens | New unique-context ~tokens | Delta | Reduction |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for scenario in scenarios:
        name = scenario["name"]
        path_groups = scenario["paths"]

        old_unique_paths = unique_paths_for_stage(
            path_groups,
            ("changed", "direct_dependencies", "pattern_files", "tests", "config", "nearby_context"),
        )
        new_unique_paths = unique_paths_for_stage(
            path_groups,
            ("changed", "direct_dependencies", "pattern_files", "tests", "config"),
        )

        old_unique_tokens = sum_tokens(old_unique_paths)
        new_unique_tokens = sum_tokens(new_unique_paths)
        delta = new_unique_tokens - old_unique_tokens
        reduction = ((old_unique_tokens - new_unique_tokens) / old_unique_tokens) * 100 if old_unique_tokens else 0.0

        print(
            "| "
            f"{name} | {len(old_unique_paths)} | {len(new_unique_paths)} | "
            f"{format_int(old_unique_tokens)} | {format_int(new_unique_tokens)} | "
            f"{delta:+,} | {reduction:.1f}% |"
        )

    print()
    print("| Prompt | Old ~tokens | New ~tokens | Delta |")
    print("|---|---:|---:|---:|")
    for stage in STAGES:
        old_total = prompt_tokens["old"][stage]
        new_total = prompt_tokens["new"][stage]
        print(f"| {stage} | {format_int(old_total)} | {format_int(new_total)} | {new_total - old_total:+,} |")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
