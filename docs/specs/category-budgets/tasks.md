# Tasks: Category Budgets

Status: IN PROGRESS
Spec: requirements.md, design.md

Rules:
- Execute tasks in order. Tasks 3 and 4 both touch cli.py; do not parallelise them.
- Write tests before implementation within each task.
- Run `python scripts/verify.py` after every task. Do not proceed to the next task until it prints VERIFY PASS.
- No task touches more than 3 files.

---

## Task 1 — Schema migration v2 → v3

**Goal**: Teach the store about the new `"budgets"` top-level key.
All subsequent tasks depend on this being correct first.

Files touched (3):
- `src/ledgerlite/store.py`
- `fixtures/ledger_v2.json`
- `tests/test_store.py`

Steps (follow ledgerlite-migration skill exactly):
1. Create `fixtures/ledger_v2.json` — schema_version 2, two entries with
   day/category/amount/currency, no "budgets" key. Never modify after creation.
2. In `store.py`:
   - Bump `SCHEMA_VERSION` from 2 to 3.
   - Add `_migrate_v2_to_v3`: pure function, calls `data.setdefault("budgets", {})`, returns data.
   - Register `MIGRATIONS[2] = _migrate_v2_to_v3`.
   - Update `load` signature to return `tuple[list[Entry], dict[str, Decimal]]`.
     Deserialise budgets as `{k: Decimal(v) for k, v in data["budgets"].items()}`.
   - Update `save` signature to accept `budgets: dict[str, Decimal]`.
     Serialise as `{k: str(v) for k, v in budgets.items()}` in the payload.
3. Update all existing callers of `store.load` / `store.save` in `cli.py`
   to unpack/pass the budgets tuple. Existing commands pass budgets through unchanged.
4. In `tests/test_store.py`:
   - Add `test_migrate_v2_fixture`: load fixture, assert budgets == {}, save to tmp,
     assert schema_version == 3 in raw JSON.
   - Add `test_save_then_load_with_budgets`: save with budgets, reload, assert round-trip.
   - Fix existing tests that call `store.load` / `store.save` to unpack the new tuple.

Tests added: `test_migrate_v2_fixture`, `test_save_then_load_with_budgets`
Verify: `python scripts/verify.py` → VERIFY PASS

---

## Task 2 — Budget logic module

**Goal**: Implement all budget business logic as pure/testable functions.
No CLI changes. Depends on Task 1.

Files touched (2):
- `src/ledgerlite/budget.py` (new)
- `tests/test_budget.py` (new)

Steps:
1. Write `tests/test_budget.py` first (all tests below), with stubs that fail.
2. Create `src/ledgerlite/budget.py` with:
   - `month_spent(entries, year, month) -> dict[str, Decimal]`
     Sums entry amounts per category for the given month. Decimal arithmetic only.
   - `status_rows(budgets, spent) -> list[dict]`
     Returns one dict per category that has a budget OR spending.
     Keys: category (str), budget (Decimal|None), spent (Decimal), remaining (Decimal|None).
     remaining = budget - spent (signed; negative means over-budget). None when no budget.
     Categories with no budget AND no spending are excluded.
   - `check_over_budget(budgets, entries, category, year, month) -> str | None`
     Returns a warning string if month-to-date spend for category exceeds its budget.
     Returns None if no budget set or not over budget. Never prints; caller decides stderr.
   - `set_budget(ledger, category, amount) -> None`
     Loads ledger, sets budgets[category] = amount, saves atomically.

Tests added:
- `test_month_spent_sums_correctly`
- `test_month_spent_decimal_not_float`
- `test_month_spent_ignores_other_months`
- `test_status_rows_over_budget`
- `test_status_rows_no_budget`
- `test_status_rows_excludes_no_budget_no_spend`
- `test_check_over_budget_fires`
- `test_check_over_budget_no_budget`
- `test_check_over_budget_under_budget`

Verify: `python scripts/verify.py` → VERIFY PASS

---

## Task 3 — CLI: budget set and budget status commands

**Goal**: Wire `budget set` and `budget status` into the CLI.
Depends on Tasks 1 and 2.

Files touched (2):
- `src/ledgerlite/cli.py`
- `tests/test_cli.py`

Steps:
1. Write CLI tests first (listed below), then implement.
2. In `cli.py`:
   - Import `budget` module and `Decimal`, `InvalidOperation`.
   - Add `budget` sub-parser with two sub-sub-parsers: `set` and `status`.
   - `cmd_budget_set`: parse Decimal (InvalidOperation → stderr, exit 1),
     validate > 0 (→ stderr, exit 1), call `budget.set_budget`, print confirmation to stdout, return 0.
   - `cmd_budget_status`: load store, call `budget.month_spent` and `budget.status_rows`,
     print each row to stdout. None rendered as `—`. Return 0.

Tests added:
- `test_budget_set_persists`
- `test_budget_set_invalid_amount`
- `test_budget_set_zero_amount`
- `test_budget_status_output`
- `test_budget_status_excludes_no_budget_no_spend`

Verify: `python scripts/verify.py` → VERIFY PASS

---

## Task 4 — CLI: over-budget warning on add

**Goal**: Warn to stderr when `ledgerlite add` causes a category to exceed
its monthly budget. Exit code remains 0. Depends on Tasks 1, 2, and 3.

Files touched (2):
- `src/ledgerlite/cli.py`
- `tests/test_cli.py`

Steps:
1. Write tests first (listed below), then implement.
2. In `cmd_add` in `cli.py`:
   - Unpack budgets from `store.load` (already done in Task 1).
   - After saving the entry, call `budget.check_over_budget(budgets, entries, category, year, month)`
     where year/month come from the entry's day.
   - If result is not None, `print(warning, file=sys.stderr)`.
   - Return 0 regardless.

Tests added:
- `test_add_over_budget_warns_stderr`
- `test_add_no_budget_no_warning`
- `test_add_under_budget_no_warning`

Verify: `python scripts/verify.py` → VERIFY PASS
