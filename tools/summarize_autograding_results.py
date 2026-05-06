#!/usr/bin/env python3
"""Luo yhteenvetotaulukon autograding-tuloksista.

Tarkoitettu ajettavaksi autograding-repositoryssa, johon opiskelijoiden
`results.json`-tiedostot tallennetaan nimellä `<opiskelija>-<aikaleima>.json`.
Oletuksena taulukkoon otetaan kustakin opiskelijasta uusin tulos.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

FILENAME_RE = re.compile(
    r"^(?P<student>.+)-(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.json$"
)


@dataclass
class ResultRow:
    student: str
    score: int
    total: int
    source_file: str
    timestamp: datetime


def parse_result_file(path: Path) -> ResultRow | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    score = data.get("score")
    total = data.get("total")
    if not isinstance(score, int) or not isinstance(total, int):
        return None

    ts = datetime.strptime(match.group("ts"), "%Y-%m-%dT%H-%M-%S")
    return ResultRow(
        student=match.group("student"),
        score=score,
        total=total,
        source_file=path.name,
        timestamp=ts,
    )


def collect_rows(results_dir: Path) -> list[ResultRow]:
    latest_by_student: dict[str, ResultRow] = {}

    for path in sorted(results_dir.glob("*.json")):
        row = parse_result_file(path)
        if row is None:
            continue
        current = latest_by_student.get(row.student)
        if current is None or row.timestamp > current.timestamp:
            latest_by_student[row.student] = row

    return sorted(latest_by_student.values(), key=lambda r: (r.student.lower(), r.timestamp), reverse=False)


def build_markdown(rows: list[ResultRow]) -> str:
    header = [
        "# Autograding-yhteenveto",
        "",
        "| Opiskelija | Pisteet | Viimeisin tulos | Tiedosto |",
        "|---|---:|---|---|",
    ]

    body = [
        f"| {row.student} | {row.score}/{row.total} | {row.timestamp.isoformat(sep=' ', timespec='seconds')} UTC | `{row.source_file}` |"
        for row in rows
    ]
    if not body:
        body = ["| *(ei tuloksia)* | - | - | - |"]

    return "\n".join(header + body) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Luo autograding-yhteenvetotaulukko.")
    parser.add_argument("--results-dir", default=".", help="Hakemisto jossa JSON-tulokset sijaitsevat")
    parser.add_argument("--output", default="SUMMARY.md", help="Yhteenvetotiedoston polku")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    output = Path(args.output)

    rows = collect_rows(results_dir)
    output.write_text(build_markdown(rows), encoding="utf-8")
    print(f"✅ Yhteenveto kirjoitettu: {output} ({len(rows)} opiskelijaa)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
