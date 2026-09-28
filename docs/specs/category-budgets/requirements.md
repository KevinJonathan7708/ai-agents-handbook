# Requirements: Category Budgets

Status: DRAFT (revised) — awaiting approval
Feature branch: `feature/category-budgets`

---

## 1. Overview

Add per-category monthly budgets to ledgerlite. A user can set a spending
ceiling for any category, check how much of that ceiling has been used in a
given month, and be warned in real time when a new entry pushes spending over
the limit.

---

## 2. Scope

In scope:
- `budget set <category> <amount>` command
- `budget status --year Y --month M` command
- Over-budget warning printed to stderr on `ledgerlite add`
- Persisting budgets in the ledger JSON file (schema migration v2 → v3)

Out of scope (not in this spec):
- `budget delete` / `budget unset`
- Multi-currency budget comparison
- Budget rollover across months
- Changes to the report command
- Any GUI or web interface

---

## 3. Functional Requirements

### FR-1 — Storage: `budgets` key in the ledger file
The system shall store budgets in the ledger JSON file under a top-level
`"budgets"` key. The value shall be an object mapping category name strings
to Decimal-serialised amount strings — the same serialisation already used
for `Entry.amount` (i.e. `str(Decimal(...))`, never a float literal).

Full example of the v3 on-disk format:

```json
{
  "schema_version": 3,
  "budgets": {
    "food": "5000",
    "transport": "2000.50"
  },
  "entries": [
    { "day": "2026-09-01", "category": "food", "amount": "450", "currency": "INR" }
  ]
}
```

A ledger file with no `"budgets"` key (i.e. any file written before this
feature) shall be treated as having an empty budget map. This is enforced by
the migration function, not by defensive `.get()` calls at read time.

### FR-2 — `budget set` command
Running `ledgerlite budget set <category> <amount>` shall:
1. Parse `<amount>` as a `decimal.Decimal` (never float).
2. Validate that `<amount>` is strictly positive (> 0).
3. Persist the budget for `<category>` in the ledger file atomically,
   overwriting any previous value for that category.
4. Print to stdout (exactly):
   ```
   budget <category> set to <amount>
   ```
   where `<amount>` is the canonical Decimal string (e.g. `5000`, `2500.50`).
5. Exit with code 0.

### FR-3 — `budget status` command
Running `ledgerlite budget status --year Y --month M` shall:
1. Collect all entries whose `day` falls within the calendar month Y-M.
2. Sum amounts per category for that month using `decimal.Decimal` arithmetic
   (never float). This is the month-to-date spend for each category.
3. For each category that either has a budget set OR has spending in that
   month, print one line in this format:
   ```
   <category>  budget: <budget>  spent: <spent>  remaining: <remaining>
   ```
   - `<budget>` is the stored Decimal string, or `—` if no budget is set
     for that category.
   - `<spent>` is the Decimal sum for that category in that month, or `0`
     if none.
   - `<remaining>` is `budget − spent` as a signed Decimal. If
     `spent > budget` the value will be negative (e.g. `-200`), showing the
     true overage to the user. If no budget is set, `remaining` is `—`.
4. Categories with no budget and no spending in the requested month shall
   not appear in the output (see AC-6 and FR-6).
5. Exit with code 0.

### FR-4 — Invalid amount rejection
If `<amount>` passed to `budget set` is not parseable as a Decimal, or is
a valid Decimal that is ≤ 0, the system shall:
1. Print a clear error message to stderr, e.g.:
   `Error: amount must be a positive number`
2. Exit with a nonzero exit code.
3. Leave the ledger file completely unchanged (no partial write).

### FR-5 — Over-budget warning on `ledgerlite add`
When `ledgerlite add --category C --amount A` is executed and, after the
entry is appended, the month-to-date total for category C in the entry's
calendar month exceeds C's budget, the system shall:
1. Write a warning to **stderr** (not stdout), e.g.:
   `Warning: food is over budget (spent 5200, budget 5000)`
   All amounts in the warning are Decimal strings, not floats.
2. Still write the entry to the ledger file (the add is not rolled back).
3. Exit with **code 0** — the warning is informational, not a failure.

If no budget exists for category C, no warning is printed and behaviour is
identical to the pre-feature `add` command.

### FR-6 — Behavior when no budget exists for a category
This requirement consolidates all "no budget" cases:

- `budget status`: a category with spending in the requested month but no
  budget SHALL appear with `budget: —` and `remaining: —`.
  A category with no budget AND no spending SHALL NOT appear (AC-6).
- `ledgerlite add`: no warning is printed. The add succeeds silently.
- `budget set`: if a budget already exists for the category, the new value
  overwrites it silently. The command is idempotent.
- A missing `"budgets"` key in the file is treated as an empty budget map
  after migration (FR-7). No budget is assumed to exist for any category.

### FR-7 — Schema migration v2 → v3 (ledgerlite-migration skill)
The `"budgets"` key is a new top-level field in the ledger file. This
constitutes a schema change and must follow every step of the
`ledgerlite-migration` skill in `.kiro/skills/ledgerlite-migration/SKILL.md`.
The six steps and how they apply here:

**Step 1 — Bump `SCHEMA_VERSION`**
`SCHEMA_VERSION` in `src/ledgerlite/store.py` is currently `2` (set by the
`currency` migration). It must be bumped to `3`.

**Step 2 — Register `MIGRATIONS[2]`**
A pure migration function `_migrate_v2_to_v3` must be registered as
`MIGRATIONS[2]`. It takes the raw file dict and returns the dict with
`"budgets": {}` added if the key is absent. The function must be pure: it
must not read from or write to the filesystem, and must not make network
calls.

```python
def _migrate_v2_to_v3(data: dict) -> dict:
    data.setdefault("budgets", {})
    return data

MIGRATIONS[2] = _migrate_v2_to_v3
```

**Step 3 — `Entry.to_dict` / `Entry.from_dict`**
`"budgets"` is a top-level key, not a field on `Entry`. Therefore no changes
to `Entry.to_dict` or `Entry.from_dict` in `src/ledgerlite/models.py` are
required for this migration. `store.load` and `store.save` are updated
instead (they own the top-level structure).

**Step 4 — Fixture `fixtures/ledger_v2.json`**
A fixture file `fixtures/ledger_v2.json` must be created. It must:
- Have `"schema_version": 2`
- Have a `"entries"` array with at least two entries (each with `day`,
  `category`, `amount`, `currency` — the v2 format written after the
  `currency` migration)
- Have no `"budgets"` key

This file must never be modified after creation; it is the permanent record
of the v2 on-disk format.

**Step 5 — Migration test in `tests/test_store.py`**
A test `test_migrate_v2_fixture` must be added that:
1. Calls `store.load(FIXTURES_DIR / "ledger_v2.json")`
2. Asserts that the returned budgets map equals `{}`
3. Saves the result to a `tmp_path`
4. Reads the raw JSON back and asserts `schema_version == 3`

**Step 6 — Verify gate**
`python scripts/verify.py` must print `VERIFY PASS` before the migration
task is considered done. Do not mark it complete until this is confirmed.

---

## 4. Non-Functional Requirements

### NFR-1 — Decimal precision
All budget amounts and spending totals shall be computed as `decimal.Decimal`,
never `float`. This applies to storage, arithmetic in `budget status`, and
the over-budget check in `ledgerlite add`. No `float()` conversion shall
appear in any budget code path.

### NFR-2 — Atomicity
`budget set` and `ledgerlite add` shall use the existing atomic write pattern
in `store.save` (write to `.tmp`, then `replace`). The ledger file shall
never be left in a partially-written state.

### NFR-3 — stderr vs stdout discipline
- Warnings (FR-5) go to **stderr**.
- Error messages (FR-4) go to **stderr**.
- Normal output (`budget set` confirmation, `budget status` lines) goes to
  **stdout**.
This separation ensures scripts that capture stdout are not polluted by
warnings.

### NFR-4 — No network calls
No new network calls shall be introduced. This is a local-only feature.

### NFR-5 — Verify gate
`python scripts/verify.py` must print `VERIFY PASS` after all changes.

---

## 5. Acceptance Criteria (from NOTES.md)

AC-1 (Ubiquitous): The system shall store budgets in the ledger file under a
`"budgets"` key mapping each category name to a Decimal amount.
→ Covered by FR-1, FR-7.

AC-2 (Event-driven): WHEN the user runs `budget set <category> <amount>`
THEN the system shall persist the budget and print:
`budget <category> set to <amount>`.
→ Covered by FR-2.

AC-3 (Event-driven): WHEN the user runs `budget status --year Y --month M`
THEN the system shall print each budgeted category with its budget,
month-to-date spent amount, and remaining amount for the requested month.
→ Covered by FR-3.

AC-4 (Unwanted): IF `<amount>` is not a positive Decimal THEN the system
shall reject the command, print a clear error to stderr, return a nonzero
exit code, and leave the stored budget unchanged.
→ Covered by FR-4.

AC-5 (State-driven): WHILE a category's month-to-date spend exceeds its
budget THE system shall print a warning to stderr when an entry is added to
that category, while the successful add command retains exit code 0.
→ Covered by FR-5. Exit code 0 is explicit in FR-5 step 3. Warning to
  stderr is explicit in FR-5 step 1 and NFR-3.

AC-6 (Optional): WHERE no budget exists for a category THE `budget status`
command shall not display that category unless it has spending for the
requested month.
→ Covered by FR-3 step 4 and FR-6.

---

## 6. Design checklist

The following items are explicitly present in this document:

| Item | Where |
|---|---|
| `SCHEMA_VERSION = 2` (current, before this change) | FR-7 Step 1 |
| `SCHEMA_VERSION` bumped to `3` (after this change) | FR-7 Step 1 |
| `"budgets"` key in the ledger JSON format | FR-1 (with example) |
| Migration function `_migrate_v2_to_v3` (pure, no I/O) | FR-7 Step 2 (with code) |
| `MIGRATIONS[2]` registered | FR-7 Step 2 |
| `fixtures/ledger_v2.json` with ≥ 2 entries, no `"budgets"` key | FR-7 Step 4 |
| Migration test loading v2 fixture, asserting budgets + schema_version | FR-7 Step 5 |
| All amounts as `decimal.Decimal`, never `float` | FR-1, FR-2, FR-3, NFR-1 |
| Warnings sent to stderr | FR-5 step 1, NFR-3 |
| Successful `add` retaining exit code 0 | FR-5 step 3, AC-5 |

---

## 7. Open Questions

OQ-1: Should `budget status` with no `--year`/`--month` flags default to the
current calendar month, or require both flags and error if omitted? (FR-3
currently requires both flags explicitly.)

OQ-2: The output format for `budget status` (FR-3) uses simple spacing.
Should columns be padded to a fixed width, or is the current format
sufficient for now?

OQ-3: The over-budget check in FR-5 fires based on the entry's `day`, not
today's date. If `day` is in the past or future, the check still fires for
that month. Confirm this is the intended behaviour.
