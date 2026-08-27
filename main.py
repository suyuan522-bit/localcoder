"""Command-line entry point for one LocalCoder task."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from agent import AgentCore
from config import ConfigurationError, load_llm_config
from llm_client import LLMClient
from tools.registry import ToolRegistry, register_local_tools
from tools.workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one autonomous LocalCoder task in a local workspace."
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Existing workspace directory available to local tools.",
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Natural-language coding task to complete.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_llm_config()
        workspace = Workspace(args.workspace)
        registry = ToolRegistry()
        agent = AgentCore(LLMClient(config), registry, args.task)
        register_local_tools(
            registry,
            workspace,
            agent.state.modified_files,
        )
    except (ConfigurationError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    result = agent.run()
    stream = sys.stdout if result.success else sys.stderr
    print(result.message, file=stream)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
