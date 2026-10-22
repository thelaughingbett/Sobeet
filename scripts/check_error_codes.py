#!/usr/bin/env python3
"""Keep docs/ERROR_CODES.md in sync with base/utils/errors.py.

errors.py is the source of truth for each code's HTTP status and message.
The doc owns the prose in the "When it happens" column, so this script never
generates descriptions: it checks, and with --fix it adds stub rows for you to
fill in.

Checks (exit code 1 if any fail):
  * every code defined in errors.py has a row in the doc, and vice versa
  * the HTTP status and message in the doc match errors.py
  * no code is defined twice in errors.py or listed twice in the doc
  * each _define() variable name matches its code (APT015 = _define("APT015", ...))
  * every code prefix appears in the "Code prefixes" table
  * no row still carries the TODO placeholder that --fix writes

Usage:
    python scripts/check_error_codes.py          # check only (CI, pre-commit)
    python scripts/check_error_codes.py --fix    # add missing rows, correct status/message

--fix places a new row after the code that precedes it in errors.py, so the
doc follows the same order and sections as the source, then re-aligns that table.
It never deletes rows; a code that only exists in the doc is reported for you
to remove by hand.
"""
import argparse
import ast
import re
import sys
from pathlib import Path

ERRORS_PY = "base/utils/errors.py"
DOC_MD = "docs/ERROR_CODES.md"
TODO = "TODO: describe when this happens."

CODE_RE = re.compile(r"^[A-Z]{3}\d{3}$")
ROW_RE = re.compile(r"^\|\s*`([A-Z]{3}\d{3})`\s*\|")
PREFIX_ROW_RE = re.compile(r"^\|\s*`([A-Z]{3})`\s*\|")


# ── errors.py ─────────────────────────────────────────────────────

def load_catalog(path):
    """Return ({code: (message, status)} in file order, [problems])."""
    catalog, problems = {}, []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        call = node.value
        if not (isinstance(call.func, ast.Name) and call.func.id == "_define"):
            continue
        where = f"{ERRORS_PY}:{node.lineno}"
        try:
            args = [ast.literal_eval(a) for a in call.args]
            kwargs = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
        except ValueError:
            problems.append(f"{where}: _define() arguments must be plain literals")
            continue

        names = ["code", "message", "status"]
        values = dict(zip(names, args), **kwargs)
        code = values.get("code")
        message = values.get("message")
        status = values.get("status", 400)

        if not isinstance(code, str) or not CODE_RE.match(code):
            problems.append(f"{where}: {code!r} is not a code like APT001")
            continue
        if not isinstance(message, str) or not isinstance(status, int):
            problems.append(f"{where}: {code} needs a string message and an int status")
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id != code:
            problems.append(f"{where}: variable {target.id} is defined with code {code}")
        if code in catalog:
            problems.append(f"{where}: {code} is defined more than once")
            continue
        catalog[code] = (message, status)
    return catalog, problems


# ── markdown tables ───────────────────────────────────────────────

def split_cells(line):
    inner = line.strip()
    inner = inner[1:-1] if inner.endswith("|") else inner[1:]
    return [c.strip() for c in re.split(r"(?<!\\)\|", inner)]


def _is_separator(cells):
    return all(re.fullmatch(r":?-+:?", c) for c in cells)


def render(cells):
    return "| " + " | ".join(cells) + " |"


def escape(text):
    return text.replace("|", "\\|")


def realign(lines, index):
    """Re-pad the table containing lines[index] so its columns line up."""
    start = end = index
    while start > 0 and lines[start - 1].lstrip().startswith("|"):
        start -= 1
    while end + 1 < len(lines) and lines[end + 1].lstrip().startswith("|"):
        end += 1

    table = [split_cells(line) for line in lines[start:end + 1]]
    columns = max(len(row) for row in table)
    widths = [3] * columns
    for row in table:
        if not _is_separator(row):
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

    for offset, row in enumerate(table):
        row = row + [""] * (columns - len(row))
        if _is_separator(row):
            cells = ["-" * widths[i] for i in range(columns)]
        else:
            cells = [row[i].ljust(widths[i]) for i in range(columns)]
        lines[start + offset] = render(cells)


def doc_rows(lines):
    """Return ({code: line index}, [codes listed more than once])."""
    rows, duplicates = {}, []
    for i, line in enumerate(lines):
        m = ROW_RE.match(line)
        if not m:
            continue
        code = m.group(1)
        if code in rows:
            duplicates.append(code)
        else:
            rows[code] = i
    return rows, duplicates


# ── fix ───────────────────────────────────────────────────────────

def fix_doc(lines, catalog):
    """Add missing rows and correct status/message in place. Returns a list of actions."""
    actions = []
    codes = list(catalog)
    for n, code in enumerate(codes):
        message, status = catalog[code]
        rows, _ = doc_rows(lines)

        if code in rows:
            i = rows[code]
            cells = split_cells(lines[i])
            if len(cells) >= 4 and (cells[1] != str(status) or cells[2] != escape(message)):
                cells[1], cells[2] = str(status), escape(message)
                lines[i] = render(cells)
                realign(lines, i)
                actions.append(f"updated {code} to match errors.py")
            continue

        previous = codes[n - 1] if n else None
        anchor = None
        if previous and previous[:3] == code[:3] and previous in rows:
            anchor = rows[previous]
        else:
            same_prefix = [i for c, i in rows.items() if c[:3] == code[:3]]
            if same_prefix:
                anchor = max(same_prefix)
        if anchor is None:
            actions.append(
                f"cannot add {code}: the doc has no table for prefix {code[:3]}; add one by hand"
            )
            continue

        lines.insert(anchor + 1, render([f"`{code}`", str(status), escape(message), TODO]))
        realign(lines, anchor + 1)
        actions.append(f"added {code} (fill in 'When it happens')")
    return actions


# ── check ─────────────────────────────────────────────────────────

def find_problems(lines, catalog, source_problems):
    problems = list(source_problems)
    rows, duplicates = doc_rows(lines)

    for code in duplicates:
        problems.append(f"{DOC_MD}: {code} is listed more than once")

    for code, (message, status) in catalog.items():
        if code not in rows:
            problems.append(f"{code}: defined in errors.py but missing from {DOC_MD}")
            continue
        cells = split_cells(lines[rows[code]])
        if len(cells) < 4:
            problems.append(f"{DOC_MD}: row for {code} needs 4 columns")
            continue
        if cells[1] != str(status):
            problems.append(f"{code}: HTTP is {cells[1]} in the doc but {status} in errors.py")
        if cells[2] != escape(message):
            problems.append(
                f"{code}: message is {cells[2]!r} in the doc but {message!r} in errors.py"
            )
        if TODO in cells[3]:
            problems.append(f"{code}: 'When it happens' is still the TODO placeholder")

    for code in rows:
        if code not in catalog:
            problems.append(f"{code}: in {DOC_MD} but not defined in errors.py (remove the row)")

    listed = {m.group(1) for line in lines if (m := PREFIX_ROW_RE.match(line))}
    for prefix in sorted({c[:3] for c in catalog} - listed):
        problems.append(f"{DOC_MD}: prefix {prefix} is missing from the 'Code prefixes' table")

    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fix", action="store_true",
                        help="add missing rows and correct status/message in the doc")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="project root (default: the folder above scripts/)")
    args = parser.parse_args(argv)

    errors_path = args.root / ERRORS_PY
    doc_path = args.root / DOC_MD
    for path in (errors_path, doc_path):
        if not path.exists():
            print(f"Cannot find {path}", file=sys.stderr)
            return 2

    catalog, source_problems = load_catalog(errors_path)
    lines = doc_path.read_text(encoding="utf-8").split("\n")

    if args.fix:
        actions = fix_doc(lines, catalog)
        if actions:
            doc_path.write_text("\n".join(lines), encoding="utf-8")
            for action in actions:
                print(f"fixed: {action}")

    problems = find_problems(lines, catalog, source_problems)
    if problems:
        for problem in problems:
            print(f"ERROR {problem}")
        if not args.fix:
            print("\nRun with --fix to add missing rows and correct status/message.")
        return 1

    print(f"OK: {len(catalog)} error codes in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
