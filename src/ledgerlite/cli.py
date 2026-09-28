from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import budget, report, store
from .models import Entry

DEFAULT_LEDGER = Path("ledger.json")


def cmd_add(args: argparse.Namespace) -> int:
    entries, budgets = store.load(args.ledger)
    day = date.fromisoformat(args.day)
    entry = Entry(day=day, category=args.category, amount=Decimal(args.amount))
    entries.append(entry)
    store.save(args.ledger, entries, budgets)
    print(f"added {args.category} {args.amount} on {args.day}")
    warning = budget.check_over_budget(budgets, entries, args.category, day.year, day.month)
    if warning:
        print(warning, file=sys.stderr)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    entries, _budgets = store.load(args.ledger)
    entries = sorted(entries, key=lambda e: e.day)
    if args.last:
        entries = entries[-args.last :]
    for e in entries:
        print(f"{e.day.isoformat()}  {e.category:<16}{e.amount:>12.2f}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    entries, _budgets = store.load(args.ledger)
    month_entries = report.entries_in_month(entries, args.year, args.month)
    print(report.format_report(args.year, args.month, report.totals_by_category(month_entries)))
    return 0


def cmd_budget_set(args: argparse.Namespace) -> int:
    try:
        amount = Decimal(args.amount)
    except InvalidOperation:
        print("Error: amount must be a positive number", file=sys.stderr)
        return 1
    if amount <= 0:
        print("Error: amount must be a positive number", file=sys.stderr)
        return 1
    budget.set_budget(args.ledger, args.category, amount)
    print(f"budget {args.category} set to {amount}")
    return 0


def cmd_budget_status(args: argparse.Namespace) -> int:
    entries, budgets = store.load(args.ledger)
    spent = budget.month_spent(entries, args.year, args.month)
    rows = budget.status_rows(budgets, spent)
    for row in rows:
        b = str(row["budget"]) if row["budget"] is not None else "\u2014"
        r = str(row["remaining"]) if row["remaining"] is not None else "\u2014"
        print(
            f"{row['category']}  budget: {b}  spent: {row['spent']}  remaining: {r}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ledgerlite", description="Tiny expense ledger.")
    p.add_argument(
        "--ledger", type=Path, default=DEFAULT_LEDGER, help="ledger file (default: ledger.json)"
    )
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="add an entry")
    a.add_argument("--day", default=date.today().isoformat())
    a.add_argument("--category", required=True)
    a.add_argument("--amount", required=True)
    a.set_defaults(func=cmd_add)

    ls = sub.add_parser("list", help="list entries")
    ls.add_argument("--last", type=int, default=0, help="show only the last N entries")
    ls.set_defaults(func=cmd_list)

    r = sub.add_parser("report", help="monthly totals by category")
    r.add_argument("--year", type=int, required=True)
    r.add_argument("--month", type=int, required=True)
    r.set_defaults(func=cmd_report)

    bud = sub.add_parser("budget", help="manage category budgets")
    bud_sub = bud.add_subparsers(dest="budget_command", required=True)

    bs = bud_sub.add_parser("set", help="set a monthly budget for a category")
    bs.add_argument("category")
    bs.add_argument("amount")
    bs.set_defaults(func=cmd_budget_set)

    bst = bud_sub.add_parser("status", help="show budget vs spend for a month")
    bst.add_argument("--year", type=int, required=True)
    bst.add_argument("--month", type=int, required=True)
    bst.set_defaults(func=cmd_budget_status)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
