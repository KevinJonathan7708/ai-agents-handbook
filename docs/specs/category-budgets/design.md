# Design: Category Budgets

Status: DRAFT — awaiting approval
Requires approval of: requirements.md

---

## 1. Module structure

No new top-level module is introduced. Changes are confined to four existing
files plus one new file:

```
src/ledgerlite/
    store.py        — schema version bump, migration, load/save budgets map
    models.py       — no changes (budgets is a top-level key, not an Entry field)
    budget.py       — NEW: pure functions for budget logic (set, status, warning)
    cli.py          — new `budget` subcommand wired to budget.py functions

tests/
    test_store.py   — migration test for v2 fixture
    test_budget.py  — NEW: unit tests for all budget logic

fixtures/
    ledger_v2.json  — NEW: permanent snapshot of the v2 on-disk format
```

`budget.py` contains only pure functions and one thin I/O wrapper. It has no
direct dependency on `cli.py`, making it independently testable.

---

## 2. Data model

### 2.1 On-disk format (v3)

`store.save` writes the following top-level structure:

```json
{
  "schema_version": 3,
  "budgets": {
    "food": "5000",
    "transport": "2000.50"
  },
  "entries": [...]
}
```

`"budgets"` is a `dict[str, str]` on disk. Keys are category names. Values
are Decimal amounts serialised with `str(Decimal(...))` — identical to how
`Entry.amount` is serialised. Float literals never appear.

### 2.2 In-memory representation

`store.load` returns a tuple `(entries, budgets)` after this change:

```python
def load(path: Path) -> tuple[list[Entry], dict[str, Decimal]]:
    ...
    budgets = {k: Decimal(v) for k, v in data.get("budgets", {}).items()}
    return entries, budgets
```

`store.save` accepts both:

```python
def save(path: Path, entries: list[Entry], budgets: dict[str, Decimal]) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "budgets": {k: str(v) for k, v in budgets.items()},
        "entries": [e.to_dict() for e in entries],
    }
    ...  # atomic write unchanged
```

All callers of `store.load` and `store.save` must be updated to pass/unpack
the budgets map. Existing CLI commands (`add`, `list`, `report`) pass the
budgets through unchanged.

### 2.3 `Entry` — no changes

`Entry`, `Entry.to_dict`, and `Entry.from_dict` in `models.py` are not
modified. Budgets are not entry-level data.

---

## 3. Schema migration (ledgerlite-migration skill, six steps)

This section maps each step of the migration skill to the concrete change.

### Step 1 — Bump SCHEMA_VERSION
`SCHEMA_VERSION` in `store.py` is currently `2` (set by the currency
migration). It is bumped to `3`.

### Step 2 — Register MIGRATIONS[2]
```python
def _migrate_v2_to_v3(data: dict) -> dict:
    """Add top-level budgets map to files that pre-date this feature."""
    data.setdefault("budgets", {})
    return data

MIGRATIONS[2] = _migrate_v2_to_v3
```
The function is pure: it reads and writes only the dict argument. No
filesystem access, no network calls.

### Step 3 — Entry.to_dict / Entry.from_dict
No changes required. `"budgets"` is a top-level key owned by `store`, not a
field on `Entry`.

### Step 4 — Fixture fixtures/ledger_v2.json
```json
{
  "schema_version": 2,
  "entries": [
    { "day": "2026-09-01", "category": "food",      "amount": "450",    "currency": "INR" },
    { "day": "2026-09-03", "category": "transport",  "amount": "120.50", "currency": "INR" }
  ]
}
```
No `"budgets"` key. Two entries in v2 format (day/category/amount/currency).
This file must never be modified after creation.

### Step 5 — Migration test
In `tests/test_store.py`:
```python
def test_migrate_v2_fixture(tmp_path):
    entries, budgets = store.load(FIXTURES_DIR / "ledger_v2.json")
    assert budgets == {}
    assert len(entries) == 2
    store.save(tmp_path / "out.json", entries, budgets)
    data = json.loads((tmp_path / "out.json").read_text())
    assert data["schema_version"] == 3
```

### Step 6 — Verify gate
`python scripts/verify.py` must print `VERIFY PASS` before the migration
task is marked done.

---

## 4. Budget module: budget.py

All business logic lives here. No I/O except via `store`.

### 4.1 `set_budget`
```python
def set_budget(
    ledger: Path,
    category: str,
    amount: Decimal,
) -> None:
    """Persist a budget for category. Overwrites any existing value."""
    entries, budgets = store.load(ledger)
    budgets[category] = amount
    store.save(ledger, entries, budgets)
```

### 4.2 `month_spent`
```python
def month_spent(entries: list[Entry], year: int, month: int) -> dict[str, Decimal]:
    """Return total Decimal spend per category for the given calendar month."""
    totals: dict[str, Decimal] = {}
    for e in entries:
        if e.day.year == year and e.day.month == month:
            totals[e.category] = totals.get(e.category, Decimal(0)) + e.amount
    return totals
```
Uses `Decimal` arithmetic throughout. No `float()` calls.

### 4.3 `status_rows`
```python
def status_rows(
    budgets: dict[str, Decimal],
    spent: dict[str, Decimal],
) -> list[dict]:
    """
    Return one row per category that has a budget OR has spending.
    Each row: {category, budget, spent, remaining}.
    budget and remaining are Decimal or None (displayed as '—').
    """
```
Categories with neither a budget nor spending are excluded (AC-6).
`remaining = budget - spent`; if `spent > budget` the result is negative —
shown as-is to expose the true overage. If no budget, both `budget` and
`remaining` are `None`.

### 4.4 `check_over_budget` (called from cmd_add)
```python
def check_over_budget(
    budgets: dict[str, Decimal],
    entries: list[Entry],
    category: str,
    year: int,
    month: int,
) -> str | None:
    """
    Return a warning string if category is over budget for year/month,
    or None if not over budget or no budget set.
    """
```
Returns a string rather than printing — keeps I/O out of business logic and
makes the function trivially testable.

---

## 5. CLI wiring: cli.py changes

### 5.1 New `budget` subcommand

```
ledgerlite budget set <category> <amount>
ledgerlite budget status --year Y --month M
```

`budget` is a sub-parser with two sub-sub-parsers: `set` and `status`.

### 5.2 cmd_budget_set
1. Parse `amount` as `Decimal`. On `InvalidOperation`, print to stderr and
   return exit code 1. File is not touched.
2. Validate `amount > 0`. On failure, print to stderr, return exit code 1.
3. Call `budget.set_budget(args.ledger, args.category, amount)`.
4. Print `budget <category> set to <amount>` to stdout.
5. Return 0.

### 5.3 cmd_budget_status
1. Load entries and budgets via `store.load`.
2. Compute `spent = budget.month_spent(entries, args.year, args.month)`.
3. Compute rows via `budget.status_rows(budgets, spent)`.
4. Print each row to stdout in the format:
   `<category>  budget: <budget>  spent: <spent>  remaining: <remaining>`
   where `None` values are rendered as `—`.
5. Return 0.

### 5.4 cmd_add changes (over-budget warning)
After appending the entry and saving, call `budget.check_over_budget`.
If it returns a non-None string, write it to **stderr**. Return 0 regardless.

```python
warning = budget.check_over_budget(budgets, entries, ...)
if warning:
    print(warning, file=sys.stderr)
return 0   # exit code is always 0 on successful add
```

### 5.5 cmd_list and cmd_report
These commands call `store.load`, which now returns a tuple. They must unpack
it: `entries, _budgets = store.load(args.ledger)`. No other changes.

---

## 6. Error handling

| Scenario | Output | Exit code |
|---|---|---|
| `budget set` with non-Decimal amount | `Error: amount must be a positive number` → stderr | 1 |
| `budget set` with amount ≤ 0 | `Error: amount must be a positive number` → stderr | 1 |
| `add` causes over-budget | `Warning: <category> is over budget (spent X, budget Y)` → stderr | 0 |
| `add` with no budget for category | no warning | 0 |
| Corrupt ledger file | existing `json.JSONDecodeError` propagates | non-zero |
| Missing ledger file | existing behaviour: empty ledger | 0 |

stderr vs stdout discipline is enforced at the CLI layer only. `budget.py`
functions return strings; the CLI decides where they go.

---

## 7. Testing strategy

### test_budget.py (new)
Unit tests against `budget.py` functions directly — no disk I/O needed:

| Test | What it checks |
|---|---|
| `test_month_spent_sums_correctly` | Decimal totals for a given month, ignores other months |
| `test_month_spent_decimal_not_float` | Result is `Decimal`, not `float` |
| `test_status_rows_over_budget` | remaining is negative when spent > budget |
| `test_status_rows_no_budget` | budget and remaining are None for unbudgeted categories |
| `test_status_rows_excludes_empty` | category with no budget and no spend is absent |
| `test_check_over_budget_fires` | returns warning string when over |
| `test_check_over_budget_no_budget` | returns None when no budget set |
| `test_check_over_budget_under_budget` | returns None when under |

### test_store.py (additions)
| Test | What it checks |
|---|---|
| `test_migrate_v2_fixture` | v2 file loads with `budgets == {}`, saves as schema_version 3 |
| `test_save_then_load_with_budgets` | budgets round-trip correctly (Decimal preserved) |

### test_cli.py (additions)
| Test | What it checks |
|---|---|
| `test_budget_set_persists` | CLI stores the budget in the file |
| `test_budget_set_invalid_amount` | non-Decimal exits 1, file unchanged |
| `test_budget_set_zero_amount` | zero exits 1, file unchanged |
| `test_budget_status_output` | correct lines printed to stdout |
| `test_budget_status_excludes_no_budget_no_spend` | category absent when neither applies |
| `test_add_over_budget_warns_stderr` | warning on stderr, exit code 0 |
| `test_add_no_budget_no_warning` | no output to stderr when unbudgeted |

---

## 8. Files touched per task (preview for tasks.md)

| Task | Files touched |
|---|---|
| 1 — Migration | `store.py`, `fixtures/ledger_v2.json`, `tests/test_store.py` |
| 2 — Budget logic | `src/ledgerlite/budget.py` (new), `tests/test_budget.py` (new) |
| 3 — CLI: budget set + status | `src/ledgerlite/cli.py`, `tests/test_cli.py` |
| 4 — CLI: add warning | `src/ledgerlite/cli.py`, `tests/test_cli.py` |

Four tasks. Each touches ≤ 3 files. Task 1 is the migration. Tasks 3 and 4
both touch `cli.py` but are sequential (3 must land before 4 to avoid
conflicts).
