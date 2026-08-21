# ADR-001: How the batching RPC gateway is modelled

**Status:** accepted, 2026-08-21
**Applies to:** `openapi.yaml`

## Context

Schulmanager Online is not a resource-oriented HTTP API. There are about thirteen real HTTP
endpoints; everything else — 715 logical endpoints found by a static extraction of the shipped
JavaScript bundle, and that is a lower bound — goes through **one** operation:

```
POST /api/calls
{ "bundleVersion": "…",
  "requests": [ { "moduleName": "classbook", "endpointName": "get-statistics", "parameters": {…} } ] }
```

The client queues calls and flushes them on the next macrotask, so several unrelated logical calls
share one HTTP round trip. Results come back in an array **matched positionally** to `requests`, each
with its own status: `403` refused, `404` unknown endpoint pair, `500` bad parameters — and `429`,
which can arrive as a *result* status inside an HTTP 200.

OpenAPI describes HTTP operations. It has no vocabulary for "one operation carrying N logical calls",
so any OpenAPI document of this API has to choose which truth to tell.

## Options considered

### A. Honest — one path, `oneOf` over every logical call

`POST /api/calls` with `requests[]` as a `oneOf` of per-endpoint variants, each pinning `moduleName`
and `endpointName` with `const`, and a matching `oneOf` for the results.

* Accurate about the transport, and machine-checkable in principle.
* `discriminator` cannot express it: the discriminating key is the *pair*
  (`moduleName`, `endpointName`), and a discriminator takes a single property. So tooling gets an
  undiscriminated `oneOf` with dozens of branches.
* Renders as **one** operation. A documentation site built from it has a single page carrying every
  endpoint in the product — unusable as a reference, which is the point of publishing it.
* Every reader still has to work out which variant belongs to the screen they are building.

### B. Readable — a synthetic path per logical endpoint

`/api/calls:<moduleName>/<endpointName>`, one operation each, with a note that the transport batches.

* Reads like normal API documentation; tags, search and per-endpoint schemas all work.
* Technically fictional: those paths are not routes. A code generator pointed at it produces a client
  that sends requests nowhere.

### C. Both, with the fiction labelled

The real gateway stays in the document as its own operation, fully described — envelope, positional
results, result statuses, `bundleVersion` behaviour. In addition, every documented logical call gets a
synthetic path, and each of those operations carries

```yaml
x-rpc:
  moduleName: classbook
  endpointName: get-statistics
```

so the real dispatch pair is machine-readable rather than parsed back out of a path string.

## Decision

**Option C.**

The synthetic-path convention is stated in `info.description`, at the top of the rendered page, before
any operation is shown. On a synthetic operation:

* the **request body is the `parameters` object** — what goes into `requests[n].parameters`;
* the **response body is the `data` value** of the matching result;
* documented status codes are the **result** statuses inside the envelope, not HTTP statuses, and the
  shared responses `ResultRefused`, `ResultUnknownEndpoint` and `ResultParameterError` say so in their
  descriptions.

Envelope facts that no schema can carry — positional matching, `userError` without a `data` key, 429
inside a 200, `bundleVersion` required but unvalidated, `403` conflating role and booking — live in the
description of `POST /api/calls` and in the schema descriptions, not in a schema keyword pretending to
enforce them.

## Consequences

* The page is usable as a reference, and the transport is documented rather than hidden — a reader who
  starts at the top learns the envelope before they see a single synthetic path.
* **Generated clients from this document are wrong** unless the generator understands `x-rpc`. That is
  the price of option C and it is stated in the README rather than discovered.
* A machine consumer can build a correct client mechanically: read `x-rpc`, put the request body under
  `parameters`, wrap it in the envelope, read `results[n].data`.
* Tools that key on paths see a `:` in a path key. `redocly lint` accepts it, `swagger-parser`
  validates it, Redoc and Swagger UI both render it, and the colon guarantees no collision with a real
  route.

  **The separator was `#` first, and that was wrong.** A fragment inside a path key means a `$ref` is
  resolved against a URI that already carries one, and Swagger UI's resolver gives up on it:
  *"Could not resolve reference: Evaluation failed on token: components"* against every `$ref` in the
  operation. Redoc and `redocly lint` were both happy, which is exactly why it survived until the
  document was opened in an editor's preview. A colon carries no fragment semantics, so do not put the
  `#` back.
* If the vendor ever exposes the logical endpoints as real routes, the synthetic paths become real and
  the `x-rpc` extensions become redundant — a cheap migration, unlike unpicking option A.
