# Schulmanager Online API — reconstructed OpenAPI description

An **unofficial** OpenAPI 3.1 description of the HTTP API behind [Schulmanager
Online](https://www.schulmanager-online.de/), the school-administration product used by many German
schools, plus a static documentation site for it.

**The vendor publishes no API documentation and has promised nothing.** This is reverse engineering:
every endpoint, payload and permission described here can change without notice, and some of it is
inference. Do not build anything load-bearing on it without your own verification, and do not treat it
as permission to automate against a school's production system.

📖 **[Read the reference](https://tyrann0us.github.io/schulmanager-api/)** ·
🗂 **[Endpoint catalogue](https://tyrann0us.github.io/schulmanager-api/catalogue.html)**

## What is in this repository

[`openapi.yaml`](openapi.yaml) is the whole description and the only place API facts live: the
transport, the provenance of every claim, what is covered, what the product does not serve, and every
schema. This file stays out of that — it covers the repository itself.

Two things worth knowing before reading the specification, because they shape how it looks:

* The API is **one batching RPC gateway**, not a set of resources, so the document gives each
  documented logical call a synthetic path carrying an `x-rpc` extension with the real dispatch pair.
  The reasoning and the rejected alternative are in [`ADR-001-transport.md`](ADR-001-transport.md).
  A client generated from this document without understanding `x-rpc` will not work.
* Coverage is partial on purpose, and the specification says by how much. What is not described is
  listed in the generated endpoint catalogue instead of being invented.

## Where the schemas come from

Not from prose. Every response schema was taken from a recorded response, and the recordings are kept
as the fixtures in [`fixtures/`](fixtures). `scripts/check-fixtures.py` validates each fixture against
its schema, so a schema cannot drift away from the shape it was taken from without CI noticing.

Where no response was ever recorded, the operation says so. Nothing here was written from a guess about
a payload, and no write endpoint was called to find out.

## Repository layout

```
.
├── openapi.yaml              the specification (single file, OpenAPI 3.1)
├── ADR-001-transport.md      why the gateway is modelled the way it is
├── catalogue/
│   └── rpc-endpoints.json    the static extraction: 715 endpoints and their parameter names
├── docs/                     the published site (GitHub Pages)
│   ├── index.html            the API reference
│   └── catalogue.html        generated — every endpoint, marked described or not
├── fixtures/                 recorded response shapes, synthetic content
└── scripts/
    ├── build-docs.sh         assembles docs/ into a servable site
    ├── check-fixtures.py     validates every fixture against its schema
    ├── gen-catalogue.py      regenerates docs/catalogue.html
    └── requirements.txt      the two packages check-fixtures.py needs
```

## Working on it

```bash
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt

npx @redocly/cli lint openapi.yaml            # must report zero errors
.venv/bin/python scripts/check-fixtures.py    # every fixture must validate
./scripts/build-docs.sh
python3 -m http.server --directory docs 8000  # then open http://localhost:8000/
```

Only `check-fixtures.py` needs those two packages; `build-docs.sh` and `gen-catalogue.py` run on a bare
Python interpreter.

`docs/openapi.yaml` is a build artefact — the root `openapi.yaml` is the source of truth.

CI runs the same checks on every push and pull request, and an invalid specification fails the build
before anything is published.

### Changing a schema

Change the fixture first, then the schema, then run `check-fixtures.py`. If a schema and its fixture
disagree, the schema is wrong: the fixture came off the wire.

### Adding an endpoint

Only with a recorded response. Add the synthetic path with its `x-rpc` block, set `x-provenance`
honestly, and regenerate the catalogue so its coverage count moves. `verified-live` means *you* called
it and kept the response — not that it looks obvious.

## Read-only, on purpose

This describes a live system that real schools depend on. The write endpoints in this document were
documented from the client bundle and **never called**. Keep it that way: a stray `create-sick-note` is
a real absence in a real child's record.

## Licence

The specification, scripts and documentation in this repository are MIT-licensed (see
[`LICENSE`](LICENSE)). "Schulmanager Online" and the German product names quoted here belong to their
owner; this project is not affiliated with, endorsed by or supported by them.
