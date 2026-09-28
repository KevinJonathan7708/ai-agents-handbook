Chapter 5: Category budgets

Acceptance criteria:

1. Ubiquitous:
The system shall store budgets in the ledger file under a "budgets" key
mapping each category name to a Decimal amount.

2. Event-driven:
WHEN the user runs `budget set <category> <amount>`
THEN the system shall persist the budget and print:
`budget <category> set to <amount>`.

3. Event-driven:
WHEN the user runs `budget status --year Y --month M`
THEN the system shall print each budgeted category with its budget,
month-to-date spent amount, and remaining amount for the requested month.

4. Unwanted:
IF `<amount>` is not a positive Decimal
THEN the system shall reject the command, print a clear error to stderr,
return a nonzero exit code, and leave the stored budget unchanged.

5. State-driven:
WHILE a category's month-to-date spend exceeds its budget
THE system shall print a warning to stderr when an entry is added to that
category, while the successful add command retains exit code 0.

6. Optional:
WHERE no budget exists for a category
THE `budget status` command shall not display that category unless it has
spending for the requested month.
