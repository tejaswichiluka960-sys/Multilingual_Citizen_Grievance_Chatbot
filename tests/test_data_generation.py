"""Tests for the deterministic multilingual dataset generator."""

import csv

from ml.generate_data import (
    DEPARTMENT_DATA,
    HANDWRITTEN_CASES,
    build_datasets,
    generate_rows,
    split_rows,
)


def test_generated_data_covers_all_departments_and_languages() -> None:
    rows = generate_rows(rows_per_language=4)

    assert len(rows) == len(DEPARTMENT_DATA) * 5 * 4
    assert {row.department for row in rows} == set(DEPARTMENT_DATA)
    assert {row.lang for row in rows} == {"en", "hi", "te", "hinglish", "tenglish"}
    assert {row.priority for row in rows} == {"low", "medium", "high"}
    assert len({row.text for row in rows}) == len(rows)


def test_split_is_reproducible_and_disjoint() -> None:
    rows = generate_rows(rows_per_language=8, seed=7)
    train, test = split_rows(rows, seed=7)

    assert train
    assert test
    assert {row.text for row in train}.isdisjoint({row.text for row in test})
    assert [(row.text, row.lang, row.department) for row in train] == [
        (row.text, row.lang, row.department) for row in split_rows(rows, seed=7)[0]
    ]


def test_build_datasets_writes_expected_csv_files(tmp_path) -> None:
    counts = build_datasets(tmp_path, rows_per_language=4, seed=42)

    assert counts["raw"] == 200
    assert counts["handwritten_test"] == len(HANDWRITTEN_CASES)
    for filename in ("raw.csv", "train.csv", "test.csv", "handwritten_test.csv"):
        path = tmp_path / filename
        assert path.exists()
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows
        assert set(rows[0]) == {"text", "lang", "department", "intent", "priority"}
