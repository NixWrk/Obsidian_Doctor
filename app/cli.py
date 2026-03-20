from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="obsidian-doctor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Run read-only scan and save JSON report")
    scan.add_argument("--vault", required=True, type=Path, help="Path to Obsidian vault")
    scan.add_argument("--config", type=Path, help="Path to YAML config")
    scan.add_argument("--profile", default=None, help="Config profile name")
    scan.add_argument("--out", required=True, type=Path, help="Output JSON report path")

    gui = subparsers.add_parser("gui", help="Run local GUI")
    gui_group = gui.add_mutually_exclusive_group(required=True)
    gui_group.add_argument("--report", type=Path, help="Existing report JSON")
    gui_group.add_argument("--vault", type=Path, help="Vault to scan before GUI starts")
    gui.add_argument("--config", type=Path, help="Path to YAML config")
    gui.add_argument("--profile", default=None, help="Config profile name")
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", default=8765, type=int)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        from app.reporting.pipeline import run_scan_to_file

        run_scan_to_file(
            vault_path=args.vault,
            config_path=args.config,
            profile=args.profile,
            output_path=args.out,
        )
        return 0

    if args.command == "gui":
        from app.gui.web import run_gui

        run_gui(
            report_path=getattr(args, "report", None),
            vault_path=getattr(args, "vault", None),
            config_path=args.config,
            profile=args.profile,
            host=args.host,
            port=args.port,
        )
        return 0

    parser.error("Unknown command")
    return 2
