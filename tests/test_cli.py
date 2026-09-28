import json

from ledgerlite.cli import main

# ---------------------------------------------------------------------------
# Existing tests (unchanged behaviour)
# ---------------------------------------------------------------------------

def test_add_then_list(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    args = ["--ledger", str(ledger), "add", "--day", "2026-04-02"]
    args += ["--category", "food", "--amount", "99.90"]
    assert main(args) == 0
    assert main(["--ledger", str(ledger), "list"]) == 0
    out = capsys.readouterr().out
    assert "2026-04-02" in out and "food" in out and "99.90" in out


def test_list_last_n(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    for d in ("2026-04-01", "2026-04-02", "2026-04-03"):
        main(["--ledger", str(ledger), "add", "--day", d, "--category", "c", "--amount", "1"])
    capsys.readouterr()
    main(["--ledger", str(ledger), "list", "--last", "2"])
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert len(lines) == 2 and lines[0].startswith("2026-04-02")


def test_report_command(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    main([
        "--ledger", str(ledger), "add", "--day", "2026-04-02", "--category", "f", "--amount", "1"
    ])
    capsys.readouterr()
    assert main(["--ledger", str(ledger), "report", "--year", "2026", "--month", "4"]) == 0
    assert "TOTAL" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# budget set
# ---------------------------------------------------------------------------

def test_budget_set_persists(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    rc = main(["--ledger", str(ledger), "budget", "set", "food", "5000"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "budget food set to 5000" in out
    data = json.loads(ledger.read_text())
    assert data["budgets"]["food"] == "5000"


def test_budget_set_overwrites_existing(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    main(["--ledger", str(ledger), "budget", "set", "food", "5000"])
    main(["--ledger", str(ledger), "budget", "set", "food", "8000"])
    capsys.readouterr()
    data = json.loads(ledger.read_text())
    assert data["budgets"]["food"] == "8000"


def test_budget_set_invalid_amount(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    rc = main(["--ledger", str(ledger), "budget", "set", "food", "notanumber"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Error" in err
    assert not ledger.exists()


def test_budget_set_zero_amount(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    rc = main(["--ledger", str(ledger), "budget", "set", "food", "0"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Error" in err
    assert not ledger.exists()


def test_budget_set_negative_amount(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    rc = main(["--ledger", str(ledger), "budget", "set", "food", "-100"])
    assert rc == 1
    capsys.readouterr()
    assert not ledger.exists()


# ---------------------------------------------------------------------------
# budget status
# ---------------------------------------------------------------------------

def test_budget_status_output(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    main(["--ledger", str(ledger), "budget", "set", "food", "5000"])
    main([
        "--ledger", str(ledger), "add",
        "--day", "2026-09-10", "--category", "food", "--amount", "3000"
    ])
    capsys.readouterr()
    rc = main(["--ledger", str(ledger), "budget", "status", "--year", "2026", "--month", "9"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "food" in out
    assert "5000" in out
    assert "3000" in out
    assert "2000" in out


def test_budget_status_over_budget_shows_negative(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    main(["--ledger", str(ledger), "budget", "set", "food", "5000"])
    main([
        "--ledger", str(ledger), "add",
        "--day", "2026-09-10", "--category", "food", "--amount", "5200"
    ])
    capsys.readouterr()
    main(["--ledger", str(ledger), "budget", "status", "--year", "2026", "--month", "9"])
    out = capsys.readouterr().out
    assert "-200" in out


def test_budget_status_no_budget_shows_dash(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    main([
        "--ledger", str(ledger), "add",
        "--day", "2026-09-10", "--category", "food", "--amount", "200"
    ])
    capsys.readouterr()
    main(["--ledger", str(ledger), "budget", "status", "--year", "2026", "--month", "9"])
    out = capsys.readouterr().out
    assert "food" in out
    assert "\u2014" in out  # — for budget and remaining


def test_budget_status_excludes_no_budget_no_spend(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    main(["--ledger", str(ledger), "budget", "set", "food", "5000"])
    # transport has no budget, no spending in the requested month
    main([
        "--ledger", str(ledger), "add",
        "--day", "2026-08-01", "--category", "transport", "--amount", "100"
    ])
    capsys.readouterr()
    main(["--ledger", str(ledger), "budget", "status", "--year", "2026", "--month", "9"])
    out = capsys.readouterr().out
    assert "transport" not in out


# ---------------------------------------------------------------------------
# add: over-budget warning (Task 4)
# ---------------------------------------------------------------------------

def test_add_over_budget_warns_stderr(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    main(["--ledger", str(ledger), "budget", "set", "food", "5000"])
    capsys.readouterr()
    rc = main([
        "--ledger", str(ledger), "add",
        "--day", "2026-09-10", "--category", "food", "--amount", "5200"
    ])
    assert rc == 0  # exit code stays 0
    captured = capsys.readouterr()
    assert "Warning" in captured.err
    assert "food" in captured.err
    assert "over budget" in captured.err


def test_add_no_budget_no_warning(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    rc = main([
        "--ledger", str(ledger), "add",
        "--day", "2026-09-10", "--category", "food", "--amount", "99999"
    ])
    assert rc == 0
    assert capsys.readouterr().err == ""


def test_add_under_budget_no_warning(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    main(["--ledger", str(ledger), "budget", "set", "food", "5000"])
    capsys.readouterr()
    rc = main([
        "--ledger", str(ledger), "add",
        "--day", "2026-09-10", "--category", "food", "--amount", "4000"
    ])
    assert rc == 0
    assert capsys.readouterr().err == ""


def test_add_warning_does_not_pollute_stdout(tmp_path, capsys):
    """Warning must go to stderr only; stdout must contain only the add confirmation."""
    ledger = tmp_path / "l.json"
    main(["--ledger", str(ledger), "budget", "set", "food", "5000"])
    capsys.readouterr()
    main([
        "--ledger", str(ledger), "add",
        "--day", "2026-09-10", "--category", "food", "--amount", "5200"
    ])
    captured = capsys.readouterr()
    assert "Warning" not in captured.out
    assert "added" in captured.out
