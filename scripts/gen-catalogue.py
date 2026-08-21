#!/usr/bin/env python3
"""Generate docs/catalogue.html — the full endpoint inventory, marked for what is documented.

Why this page exists: the specification describes roughly forty logical endpoints, and a static
extraction of the shipped JavaScript bundle found 715. Leaving the other ~675 out entirely would make
the specification look complete; inventing schemas for them would make it wrong. So they are listed
here with their parameter *names* and nothing else, and each row says whether openapi.yaml documents
it.

Redoc drops tags that carry no operations, which is why the inventory lives on its own page rather
than in tag descriptions.

    python3 scripts/gen-catalogue.py

Requires ``pyyaml`` (see ``scripts/requirements.txt``).
"""

from __future__ import annotations

import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "catalogue" / "rpc-endpoints.json"
SPEC = ROOT / "openapi.yaml"
OUTPUT = ROOT / "docs" / "catalogue.html"

# Namespace -> (vendor product name, vendor page slug, intended audience, one-line purpose).
# Source: the vendor's public module pages, corrected against a live capture of
# main/get-bookable-modules-for-offer, which returns the vendor's own label per namespace.
# An empty slug means the namespace has no public product page.
MODULES: dict[str, tuple[str, str, str, str]] = {
    "messenger": ("Nachrichten", "nachrichten", "staff, parents, students",
                  "Direct messages with attachments and per-message reply control"),
    "letters": ("Elternbriefe", "elternbriefe", "school to parents",
                "Letters with read confirmation and attached surveys"),
    "grades": ("Noten", "noten", "teachers enter, families read",
               "Grades; visibility to families is a school setting"),
    "documents": ("Dokumente", "dokumente", "admins upload, everyone reads",
                  "Shared files in a permissioned folder tree"),
    "calendar": ("Kalender", "kalender", "school",
                 "Events in group-scoped calendars, plus a public one"),
    "classbook": ("Digitales Klassenbuch", "digitales-klassenbuch", "teachers",
                  "Attendance, lesson content, homework, per-student entries"),
    "absences": ("Fehlzeiten", "fehlzeiten", "secretariat, class teachers",
                 "Management of absences fed by the sick-note, exemption and classbook modules"),
    "sick": ("Krankmeldung", "krankmeldung", "parents",
             "Report a child ill; flows into absence management"),
    "exemptions": ("Beurlaubung", "antrag-auf-beurlaubung", "parents submit, school approves",
                   "Leave requests; granted ones flow into absence management"),
    "schedules": ("Stundenplan", "vertretungsplan-anzeige", "teachers, optionally families",
                  "Display of the timetable with substitutions merged in"),
    "tiles": ("Schwarzes Brett", "schwarzes-brett", "admins write, everyone reads",
              "Notice tiles on the dashboard"),
    "allday": ("Ganztag", "ganztag", "care staff, parents message",
               "After-school care; parents send notes about pick-up and schedule changes"),
    "exams": ("Klassenarbeiten", "klassenarbeiten", "teachers plan, families read",
              "Exam dates with per-class weekly limits"),
    "behaviorgrades": ("Kopfnoten", "kopfnoten", "subject teachers propose, form teacher decides",
                       "Conduct and learning-behaviour marks"),
    "learningdevelopment": ("LEG", "leg", "teachers",
                            "Competence statements and forms for learning-development talks"),
    "learning": ("Lernen", "lernen", "teachers, students", "Materials, submissions, feedback"),
    "electives": ("Wahlfächer", "wahlfaecher", "students choose, algorithm assigns",
                  "Elective and seminar allocation"),
    "invoicing": ("Zahlungen", "geld-einsammeln", "school bills, parents pay",
                  "Cashless collection with bank-transfer matching"),
    "detention": ("Nacharbeit", "nacharbeit", "admin schedules, parents notified",
                  "Detention sessions and their supervision"),
    "studentrecord": ("Schülerakte", "schuelerakte", "staff, per-category access",
                      "Behaviour observations and disciplinary measures"),
    "schoolinformation": ("Schulinformationen", "schulinformationen", "teachers",
                          "Student master data: contacts, allergies, custom fields"),
    "schoolregistration": ("Schulanmeldung", "schulanmeldung", "parents",
                           "Online enrolment during the registration period"),
    "resources": ("Ressourcen", "ressourcenbuchung", "teachers",
                  "Booking rooms and equipment; no family role"),
    "video": ("Videokonferenzen", "videokonferenzen", "teachers host",
              "Meetings joined from calendar invitations"),
    "certificates": ("Zeugnisse", "zeugnisse", "teachers",
                     "Collaborative report-card creation, output as PDF"),
    "certificateconference": ("Zeugniskonferenz", "zeugniskonferenz", "staff",
                              "Grade conferences, at-risk detection, warning letters"),
    "timetabling": ("Stundenplanung", "stundenplanung", "admins", "Construction of the timetable"),
    "substitutions": ("Vertretungsplanung", "vertretungsplanung", "admins",
                      "Creation of substitution plans"),
    "overtime": ("Mehrarbeit", "mehrarbeit", "admins", "Teacher plus/minus hours"),
    "infoscreen": ("Infoscreen", "infoscreen", "school building",
                   "Public screens showing substitutions and dates"),
    "conferences": ("Elternsprechtag", "elternsprechtag", "school, parents",
                    "Parents' evening slot booking (vendor label from the live catalogue)"),
    "parenttalks": ("Elterngespräche", "elterngespraeche", "school, parents",
                    "Individual parent-teacher talks (vendor label from the live catalogue)"),
    "meetings": ("Sprechstunden", "sprechstunden", "teachers, parents",
                 "Teacher office hours"),
    "gradereports": ("Zwischenberichte", "", "teachers",
                     "Interim reports; named by the live catalogue, absent from the marketing site"),
    # No public product page: internal surfaces.
    "main": ("", "", "internal", "Shared surface: authentication, settings, poqa, terms"),
    "su": ("", "", "internal", "Evidently the vendor's own support console"),
    "schooldata": ("", "", "internal", "Institution administration; active but not for sale"),
    "studentmanagement": ("", "", "internal", "Student master-data administration"),
    "externalapplicationmanagement": ("", "", "internal", "External application credentials"),
    "corona": ("", "", "internal", "Legacy"),
    "gfs": ("", "", "internal", "Likely part of Noten: the Baden-Württemberg presentation grade"),
}

INTERNAL = {name for name, meta in MODULES.items() if meta[2] == "internal"}


def documented_pairs() -> set[tuple[str, str]]:
    """(moduleName, endpointName) pairs that openapi.yaml actually describes, read from x-rpc.

    Uses pyyaml when it is installed and falls back to a line scan when it is not, so that building
    the site needs nothing but a Python interpreter. The fallback is safe because it looks for one
    fixed two-line shape and nothing else:

        x-rpc:
          moduleName: classbook
          endpointName: get-statistics

    ``scripts/check-fixtures.py`` still needs the real parser — validating schemas against fixtures is
    the check that must not be approximated.
    """
    text = SPEC.read_text(encoding="utf-8")
    try:
        import yaml
    except ModuleNotFoundError:
        pairs = set()
        pattern = re.compile(
            r"^\s*x-rpc:\s*\n\s*moduleName:\s*(\S+)\s*\n\s*endpointName:\s*(\S+)\s*$",
            re.MULTILINE,
        )
        for module, endpoint in pattern.findall(text):
            pairs.add((module.strip("'\""), endpoint.strip("'\"")))
        if not pairs:
            sys.exit("found no x-rpc blocks — install pyyaml and re-run: "
                     "pip install -r scripts/requirements.txt")
        return pairs

    spec = yaml.safe_load(text)
    pairs = set()
    for item in spec.get("paths", {}).values():
        for operation in item.values():
            if isinstance(operation, dict) and "x-rpc" in operation:
                rpc = operation["x-rpc"]
                pairs.add((rpc["moduleName"], rpc["endpointName"]))
    return pairs


def main() -> int:
    endpoints = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    documented = documented_pairs()

    by_module: dict[str, list[dict]] = defaultdict(list)
    for entry in endpoints:
        by_module[entry["module"] or "(runtime-resolved)"].append(entry)

    total = len(endpoints)
    described = len(documented)

    def esc(value: str) -> str:
        return html.escape(value, quote=False)

    rows = []
    for module in sorted(by_module, key=lambda name: (name == "(runtime-resolved)", name)):
        entries = sorted(by_module[module], key=lambda item: item["endpoint"])
        label, slug, audience, purpose = MODULES.get(module, ("", "", "unmapped", ""))
        badges = []
        if module in INTERNAL:
            badges.append('<span class="badge internal">internal</span>')
        if module == "(runtime-resolved)":
            badges.append('<span class="badge internal">module decided at runtime</span>')
        heading = f"<code>{esc(module)}</code>"
        if label:
            heading += f" — {esc(label)}"
        link = (f' <a href="https://www.schulmanager-online.de/module.{slug}.html">product page</a>'
                if slug else "")
        described_here = sum(1 for e in entries if (module, e["endpoint"]) in documented)

        body = [f"<h3 id=\"{esc(module)}\">{heading} {' '.join(badges)}</h3>"]
        if purpose:
            body.append(f"<p class=\"meta\">{esc(purpose)}. Intended audience: {esc(audience)}."
                        f"{link}</p>")
        body.append(f"<p class=\"meta\">{len(entries)} endpoints, {described_here} described in "
                    f"openapi.yaml.</p>")
        body.append('<table><thead><tr><th>Endpoint</th><th>Parameter names</th>'
                    '<th>In the specification</th></tr></thead><tbody>')
        for entry in entries:
            params = ", ".join(f"<code>{esc(p)}</code>" for p in entry["params"])
            if not params:
                params = ('<span class="none">no arguments</span>'
                          if entry.get("calledWithNoParams") else
                          '<span class="none">not statically resolvable</span>')
            mark = ('<span class="yes">described</span>'
                    if (module, entry["endpoint"]) in documented
                    else '<span class="no">not described</span>')
            body.append(f"<tr><td><code>{esc(entry['endpoint'])}</code></td>"
                        f"<td>{params}</td><td>{mark}</td></tr>")
        body.append("</tbody></table>")
        rows.append("\n".join(body))

    nav = " · ".join(
        f'<a href="#{esc(module)}">{esc(module)}</a>'
        for module in sorted(by_module, key=lambda name: (name == "(runtime-resolved)", name))
    )

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Endpoint catalogue — Schulmanager Online API (reconstructed)</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial,
    sans-serif; margin: 0 auto; max-width: 62rem; padding: 1.5rem 1rem 4rem; line-height: 1.5; }}
  h1 {{ margin-bottom: 0.25rem; }}
  h3 {{ margin-top: 2.25rem; border-top: 1px solid #8884; padding-top: 1rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 0.3rem 0.5rem; border-bottom: 1px solid #8883;
    vertical-align: top; }}
  th {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; opacity: 0.7; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.86em; }}
  .meta {{ opacity: 0.8; margin: 0.25rem 0; }}
  .badge {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
    border: 1px solid currentColor; border-radius: 999px; padding: 0.1rem 0.5rem;
    vertical-align: middle; }}
  .internal {{ color: #b55; }}
  .yes {{ color: #2a7; }}
  .no {{ opacity: 0.55; }}
  .none {{ opacity: 0.55; font-style: italic; }}
  .warn {{ border-left: 4px solid #d9a400; background: #d9a40018; padding: 0.75rem 1rem;
    margin: 1.25rem 0; }}
  nav {{ font-size: 0.85rem; opacity: 0.85; margin: 1rem 0 0; }}
  .wrap {{ overflow-x: auto; }}
</style>
</head>
<body>
<h1>Endpoint catalogue</h1>
<p class="meta"><a href="./index.html">← API reference</a> · generated by
<code>scripts/gen-catalogue.py</code> — do not edit by hand.</p>

<div class="warn">
  <strong>{total} logical endpoints, {described} of them described.</strong>
  This list comes from a <em>static</em> extraction of the shipped JavaScript bundle: it proves that an
  endpoint name and its parameter <em>names</em> exist at some call site, and nothing else. Parameter
  types, optionality, nesting and response shapes are unknown, minification having destroyed them; the
  count is a lower bound, taken from one build, and the bundle has been redeployed since.
  Rows marked <span class="no">not described</span> have never been called from here.
</div>

<p class="meta">Namespaces with no public product page are marked
<span class="badge internal">internal</span>: they are the vendor's own plumbing and support tooling,
not a customer API. Access is enforced <strong>per endpoint</strong>, so neither the audience column
nor a module's absence from this document tells you what a given account may call.</p>

<nav>{nav}</nav>

<div class="wrap">
{"".join(rows)}
</div>
</body>
</html>
"""
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)} — {total} endpoints, {described} described")
    return 0


if __name__ == "__main__":
    sys.exit(main())
