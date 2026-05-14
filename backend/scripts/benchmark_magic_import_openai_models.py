#!/usr/bin/env python
"""Compare OpenAI model cost and latency for a representative Magic Import call."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.magic_import import ExtractionHint, Snippet  # noqa: E402
from app.services.magic_import.llm.openai_provider import OpenAIProvider  # noqa: E402


DEFAULT_MODELS = ("gpt-4o-mini", "gpt-5.5")
DEFAULT_OUTPUT = Path(".benchmarks/magic-import-openai-models.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the same small Magic Import extraction prompt against one or more "
            "OpenAI models and write latency/token metrics as JSON."
        )
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help="OpenAI model IDs to compare.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Number of live calls per model.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Maximum output tokens for each extraction call.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path for the JSON benchmark report.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call OpenAI; only emit prompt-size estimates.",
    )
    return parser.parse_args()


def sample_hints() -> list[ExtractionHint]:
    return [
        ExtractionHint(
            path="Nameplate.ManufacturerName",
            label="Manufacturer Name",
            element_type="MultiLanguageProperty",
            value_type="xs:string",
            keywords=["manufacturer", "brand", "company"],
            required=True,
        ),
        ExtractionHint(
            path="Nameplate.ManufacturerProductDesignation",
            label="Product Designation",
            element_type="MultiLanguageProperty",
            value_type="xs:string",
            keywords=["product", "type", "designation", "model"],
            required=True,
        ),
        ExtractionHint(
            path="Nameplate.SerialNumber",
            label="Serial Number",
            element_type="Property",
            value_type="xs:string",
            keywords=["serial", "s/n", "sn"],
            required=False,
        ),
        ExtractionHint(
            path="Nameplate.YearOfConstruction",
            label="Year of Construction",
            element_type="Property",
            value_type="xs:gYear",
            keywords=["year", "manufactured", "construction"],
            required=False,
        ),
        ExtractionHint(
            path="Nameplate.MainsVoltage",
            label="Mains Voltage",
            element_type="Property",
            value_type="xs:string",
            keywords=["voltage", "rated", "supply", "V"],
            required=False,
        ),
    ]


def sample_snippets() -> list[Snippet]:
    return [
        Snippet(
            text=(
                "Industrial Sensor ZX-3100\n"
                "Manufacturer: Example Automation GmbH\n"
                "Type: ZX-3100-PN Digital Pressure Sensor\n"
                "Serial No.: SN-24-01873\n"
                "Year of construction: 2024"
            ),
            page=0,
            start_word_idx=0,
            end_word_idx=25,
            score=0.98,
        ),
        Snippet(
            text=(
                "Electrical data: supply voltage 24 V DC, current consumption "
                "max. 180 mA. Protection class IP67. Operating temperature "
                "-20 C to +70 C."
            ),
            page=1,
            start_word_idx=40,
            end_word_idx=70,
            score=0.86,
        ),
    ]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def prompt_estimate(model: str, hints: list[ExtractionHint], snippets: list[Snippet]) -> dict[str, Any]:
    provider = OpenAIProvider(api_key="sk-dry-run", model=model)
    system_prompt = provider._build_responses_system_prompt()
    user_prompt = provider._build_responses_user_prompt(hints, snippets)
    prompt_chars = len(system_prompt) + len(user_prompt)
    return {
        "model": model,
        "prompt_chars": prompt_chars,
        "estimated_prompt_tokens": estimate_tokens(system_prompt) + estimate_tokens(user_prompt),
        "supports_reasoning_controls": provider._supports_reasoning_controls(),
    }


async def run_model(
    model: str,
    api_key: str,
    hints: list[ExtractionHint],
    snippets: list[Snippet],
    repeats: int,
    max_tokens: int,
) -> dict[str, Any]:
    provider = OpenAIProvider(api_key=api_key, model=model)
    runs: list[dict[str, Any]] = []

    for index in range(repeats):
        started = time.perf_counter()
        response = await provider.generate_candidates(
            hints=hints,
            snippets=snippets,
            max_tokens=max_tokens,
        )
        latency_seconds = time.perf_counter() - started
        runs.append(
            {
                "run": index + 1,
                "latency_seconds": round(latency_seconds, 3),
                "tokens_used": response.tokens_used,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "candidate_sets": len(response.candidate_sets),
                "not_found_candidates": sum(
                    1
                    for candidate_set in response.candidate_sets
                    for candidate in candidate_set.candidates
                    if candidate.value == "NOT_FOUND"
                ),
                "paths": [candidate_set.path for candidate_set in response.candidate_sets],
            }
        )

    latencies = [run["latency_seconds"] for run in runs]
    token_counts = [run["tokens_used"] for run in runs]
    return {
        "model": model,
        "runs": runs,
        "median_latency_seconds": statistics.median(latencies),
        "mean_tokens_used": round(statistics.fmean(token_counts), 1),
    }


async def build_report(args: argparse.Namespace) -> dict[str, Any]:
    hints = sample_hints()
    snippets = sample_snippets()
    report: dict[str, Any] = {
        "benchmark": "magic_import_openai_model_compare_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "sample": {
            "name": "synthetic_idta_nameplate_v1",
            "hint_count": len(hints),
            "snippet_count": len(snippets),
            "expected_paths": [hint.path for hint in hints],
        },
        "models": args.models,
        "repeats": args.repeats,
        "max_tokens": args.max_tokens,
        "dry_run": args.dry_run,
        "prompt_estimates": [
            prompt_estimate(model, hints, snippets) for model in args.models
        ],
        "results": [],
    }

    if args.dry_run:
        return report

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required unless --dry-run is set.")

    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1.")

    for model in args.models:
        report["results"].append(
            await run_model(
                model=model,
                api_key=api_key,
                hints=hints,
                snippets=snippets,
                repeats=args.repeats,
                max_tokens=args.max_tokens,
            )
        )

    return report


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = asyncio.run(build_report(args))
    write_report(args.output, report)
    print(f"Wrote benchmark report to {args.output}")
    if args.dry_run:
        print("Dry run only; set OPENAI_API_KEY and omit --dry-run for live metrics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
