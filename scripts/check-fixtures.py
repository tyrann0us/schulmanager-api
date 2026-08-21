#!/usr/bin/env python3
"""Validate the recorded response fixtures against the schemas in openapi.yaml.

The fixtures in ``fixtures/`` are the same ones that pin the Swift models in the
``schulmanager-native`` client: real response shapes with synthetic content. They are the only
mechanical link between this specification and observed reality, so a schema that drifts away from
them is a schema that has stopped describing the API.

Run it after every change to ``components.schemas``:

    python3 scripts/check-fixtures.py

Requires ``pyyaml`` and ``jsonschema`` (see ``scripts/requirements.txt``).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "openapi.yaml"
FIXTURES = ROOT / "fixtures"

# fixture file -> (pointer into the fixture, schema name, wrap in an array?)
# A pointer of "" means the whole document.
CASES: list[tuple[str, str, str, bool]] = [
    ("absences.json", "absences", "StudentAbsence", True),
    ("allday.json", "offers", "AlldayOffer", True),
    ("allday.json", "messages", "AlldayMessage", True),
    ("calendar.json", "events", "EventsResponse", False),
    ("calendar.json", "categories", "EventCategory", True),
    ("classbook-statistics.json", "bySubject", "SubjectAbsenceStatistic", True),
    ("classbook-statistics.json", "byTime", "TimeAbsenceStatisticMap", False),
    ("classbook-statistics.json", "entryTypes", "StudentEntryType", True),
    ("documents.json", "rootFolder", "DocumentFolder", False),
    ("documents.json", "rootContents", "FolderContents", False),
    ("documents.json", "documentWithFile", "SchoolDocument", False),
    ("exemptions.json", "requests", "ExemptionRequest", True),
    ("grading-information.json", "", "GradingInformation", False),
    ("invoicing.json", "invoices", "StudentInvoice", True),
    ("invoicing.json", "items", "StudentItem", True),
    ("parent-talks.json", "rounds", "ParentTalkRound", True),
    ("parent-talks.json", "proposals", "ParentTalkProposal", True),
    ("parent-talks.json", "teachers", "ParentTalkTeacher", True),
    ("sick-notes.json", "notes", "SickNote", True),
    ("subjects.json", "", "Subject", True),
    ("tiles.json", "tiles", "Tile", True),
    ("timetable.json", "classHours", "ClassHour", True),
    ("timetable.json", "courses", "Course", True),
    ("timetable.json", "lessons", "Lesson", True),
]


def load_schemas() -> dict:
    """Return ``components.schemas`` with refs rewritten to ``$defs``.

    OpenAPI 3.1 schemas *are* JSON Schema 2020-12, so the only adaptation needed is the location of
    the definitions: rewriting ``#/components/schemas/`` to ``#/$defs/`` lets a plain validator
    resolve them without a registry.
    """
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("pyyaml is missing. Install it: pip install -r scripts/requirements.txt")

    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    schemas = copy.deepcopy(spec["components"]["schemas"])
    text = json.dumps(schemas).replace("#/components/schemas/", "#/$defs/")
    return json.loads(text)


def main() -> int:
    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError:
        sys.exit("jsonschema is missing. Install it: pip install -r scripts/requirements.txt")

    defs = load_schemas()
    failures = 0
    checked = 0

    for filename, pointer, schema_name, is_array in CASES:
        path = FIXTURES / filename
        if not path.exists():
            print(f"FAIL {filename}: missing fixture")
            failures += 1
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        instance = document if pointer == "" else document.get(pointer)
        if instance is None:
            print(f"FAIL {filename}#{pointer}: key not present in fixture")
            failures += 1
            continue
        if schema_name not in defs:
            print(f"FAIL {filename}#{pointer}: schema {schema_name} not in openapi.yaml")
            failures += 1
            continue

        target = {"$ref": f"#/$defs/{schema_name}"}
        if is_array:
            target = {"type": "array", "items": target}
        validator = Draft202012Validator({"$defs": defs, **target})

        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
        checked += 1
        label = f"{filename}#{pointer or '/'} -> {schema_name}{'[]' if is_array else ''}"
        if errors:
            failures += 1
            print(f"FAIL {label}")
            for error in errors[:5]:
                location = "/".join(str(part) for part in error.absolute_path) or "(root)"
                print(f"       {location}: {error.message}")
            if len(errors) > 5:
                print(f"       … and {len(errors) - 5} more")
        else:
            print(f"ok   {label}")

    print(f"\n{checked} fixture(s) checked, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
