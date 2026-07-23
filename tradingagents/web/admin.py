"""Local backup/restore CLI using server-controlled backup identifiers."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from tradingagents.persistence import BackupService, Database


def main() -> None:
    parser = argparse.ArgumentParser(prog="tradingagents-web-admin")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup")
    commands.add_parser("list")
    for name in ("preview", "restore"):
        command = commands.add_parser(name)
        command.add_argument("backup_id")
    args = parser.parse_args()
    database = Database(os.getenv(
        "TRADINGAGENTS_WEB_DB_PATH",
        str(Path.home() / ".tradingagents" / "web" / "tradingagents.db"),
    ))
    service = BackupService(database)
    if args.command == "backup":
        result = asdict(service.create())
    elif args.command == "list":
        result = {"items": [asdict(item) for item in service.list()]}
    elif args.command == "preview":
        result = asdict(service.preview(args.backup_id))
    else:
        result = {**asdict(service.restore(args.backup_id)), "restored": True}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
