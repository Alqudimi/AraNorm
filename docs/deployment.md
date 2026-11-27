# Production Deployment Guide

**AraNorm v1.15.0** · HTTP service · `PipelineRuntime` · hot reload · containers

AraNorm ships with everything needed to serve Arabic normalization in
production using only the Python standard library — no web framework, no
broker, no database. This guide covers the three deployment levels, in
increasing order of operational sophistication:

1. **Embed** — import the pipeline into your own application or worker.
2. **Serve** — run the built-in HTTP service (`aranorm serve`) behind a
   reverse proxy.
3. **Manage configuration** — drive a long-lived service with versioned
   `PipelineConfig` / `PipelineSpec` files, atomic hot reload, and
   degradation-aware health reporting.

A fourth concern — crash-safe batch processing of large files — is covered in
the companion [streaming guide](streaming.md), including the opt-in
`POST /v1/stream` endpoint.

---

## Table of contents

1. [Level 1 — Embedding in an application](#level-1--embedding-in-an-application)
2. [Level 2 — The HTTP service](#level-2--the-http-service)
   - [Starting the server](#starting-the-server)
   - [Endpoints reference](#endpoints-reference)
   - [Verified curl walkthrough](#verified-curl-walkthrough)
   - [Error mapping](#error-mapping)
   - [Health checks for orchestrators](#health-checks-for-orchestrators)
   - [Graceful degradation](#graceful-degradation)
3. [Level 3 — Configuration management](#level-3--configuration-management)
   - [`PipelineConfig` files](#pipelineconfig-files)
   - [`PipelineSpec` — portable, fingerprinted pipelines](#pipelinespec--portable-fingerprinted-pipelines)
   - [Snapshots](#snapshots)
   - [Atomic hot reload](#atomic-hot-reload)
4. [Scaling](#scaling)
5. [Security hardening](#security-hardening)
6. [Docker recipe](#docker-recipe)
7. [Monitoring](#monitoring)
8. [Operations runbook](#operations-runbook)

---

## Level 1 — Embedding in an application

For batch workers, notebooks, and applications that normalize text inline,
the pipeline object itself is the deployment unit. The single most important
rule: **build the pipeline once, reuse it everywhere.**

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))

result = pipeline.process("السَّلامُ عَلَيْكُم، كيف حالك؟")          # one item
results = pipeline.process_batch(["كيف حالك؟", "وين تروح؟"], batch_size=32)
```

A pipeline's configuration is immutable after construction and its internal
operational counters are lock-protected, so one instance can be shared across
threads for `process()` / `process_batch()` calls — this is precisely how the
built-in HTTP server serves concurrent requests. Workloads that need to
*change* pipeline behavior between calls should move up to `PipelineRuntime`
(below), which publishes immutable snapshots instead.

**Batching beats looping.** `process_batch(texts, batch_size=..., n_workers=...)`
amortizes per-call overhead and enables worker parallelism:

```python
results = pipeline.process_batch(
    ["سطر رقم %d" % i for i in range(1000)], batch_size=64, n_workers=2)
```

**Cache hot texts.** Duplicated inputs (boilerplate, greetings, spam
templates) are served from a thread-safe LRU wrapper — `hit_rate` tells you
whether the cache is paying for itself:

```python
from aranorm.utils import NormalizationCache

cache = NormalizationCache(pipeline, maxsize=10_000)
cache.process("مرحباً بكم في المكتبة")   # computed on first call
cache.process("مرحباً بكم في المكتبة")   # served from cache
cache.stats()  # {'hits': 1, 'misses': 1, 'size': 1, 'maxsize': 10000, 'hit_rate': 0.5}
```

**Measure, then tune workers.** Every pipeline exposes an immutable metrics
snapshot — useful for capacity math and for spotting regressions:

```python
pipeline.metrics_snapshot().to_dict()
# {'total_items': 51, 'succeeded': 51, 'failed': 0,
#  'total_time_ms': 17.701, 'average_time_ms': 0.347,
#  'throughput_per_second': 2881.193}
```

---

## Level 2 — The HTTP service

`aranorm serve` turns a pipeline into a JSON HTTP service built on the
standard library's `ThreadingHTTPServer`. It is **opt-in**: importing
`aranorm` never starts a listener, and the server module is only imported by
the `serve` command (or explicitly via `from aranorm.server import ...`).

### Starting the server

```console
$ aranorm serve --host 127.0.0.1 --port 8765 --preset standard
AraNorm server listening on http://127.0.0.1:8765
```

The banner goes to stderr; the process serves until interrupted (`Ctrl-C`),
then stops its reload watcher and closes the socket cleanly. The full flag
set:

| Flag | Default | Description |
|------|---------|-------------|
| `--host H` | `127.0.0.1` | Bind address. Use `0.0.0.0` only behind a proxy or on a trusted network. |
| `--port P` | `8765` | Bind port. |
| `--config PATH` | — | JSON/YAML `PipelineConfig` file for the initial pipeline. |
| `--spec PATH` | — | Validated `PipelineSpec` JSON file (mutually exclusive with `--config`). |
| `--preset {light,standard,deep,social_media}` | `standard` | Preset used when `--config`/`--spec` are omitted. |
| `--max-body-bytes N` | `2000000` | Request body ceiling (`DEFAULT_MAX_BODY_BYTES`); larger bodies get `413`. |
| `--reload-interval SECONDS` | `0.0` (off) | Poll the `--config`/`--spec` file for mtime changes and hot-reload. |
| `--streaming-enabled` | off | Enable `POST /v1/stream` (see [streaming.md](streaming.md)). |
| `--streaming-root PATH` | — | Confine `/v1/stream` paths to this existing directory (requires `--streaming-enabled`). |

With `--config`/`--spec` plus `--reload-interval 2.0`, a daemon thread
watches the file; editing it reconfigures the live service with zero downtime
([atomic hot reload](#atomic-hot-reload)).

### Endpoints reference

| Method | Path | Purpose | Success body |
|--------|------|---------|--------------|
| `GET` | `/health/live` | Liveness — process is up. | `{"schema_version":1,"status":"live"}` |
| `GET` | `/health/ready` | Readiness — runtime health. | health payload (below) |
| `GET` | `/v1/describe` | Machine-readable pipeline metadata. | describe payload |
| `POST` | `/v1/normalize` | Normalize one text. `{"text": "..."}` | `{"schema_version":1,"result":{...}}` |
| `POST` | `/v1/batch` | Normalize many. `{"texts":[...],"batch_size":32,"workers":1}` | `{"schema_version":1,"count":N,"results":[...]}` |
| `POST` | `/v1/stream` | Run a locked streaming session (opt-in). | `{"schema_version":1,"report":{...}}` |

All POST endpoints require `Content-Type: application/json` and a
`Content-Length` (no chunked uploads), with the body at or below
`--max-body-bytes`. Responses are UTF-8 JSON with `Cache-Control: no-store`.
Unknown paths — or GETs on POST-only paths — return a `404` JSON error.

### Verified curl walkthrough

Liveness and readiness:

```console
$ curl -s http://127.0.0.1:8765/health/live
{"schema_version":1,"status":"live"}

$ curl -s http://127.0.0.1:8765/health/ready
{"schema_version":1,"status":"ready","ready":true,"generation":0,
 "config_fingerprint":"e5144fa23504f33e7cc430627ba0ac536ba70e8690787250a19763d51628b3ed",
 "last_reload_error":null}
```

Single-item normalization (note the Arabic input is preserved verbatim, and
dialect detection is part of the result):

```console
$ curl -s -X POST http://127.0.0.1:8765/v1/normalize -H "Content-Type: application/json" \
       -d '{"text":"السَّلامُ عَلَيْكُم، شلونك اليوم؟"}'
{"schema_version":1,"result":{"original_text":"السَّلامُ عَلَيْكُم، شلونك اليوم؟",
 "normalized_text":"السلام عليكم, شلونك اليوم?","dialect":"GLF","dialect_confidence":0.66,
 "processing_metadata":{"is_msa":false},"processing_time_ms":11.828,
 "applied_steps":["remove_urls","normalize_unicode","…","fix_spacing"], ...}}
```

Batch normalization — the throughput workhorse:

```console
$ curl -s -X POST http://127.0.0.1:8765/v1/batch \
       -H "Content-Type: application/json" \
       -d '{"texts":["كيف حالك؟","وين تروح؟"],"batch_size":2,"workers":1}'
{"schema_version":1,"count":2,"results":[{"original_text":"كيف حالك؟",
 "normalized_text":"كيف حالك?","dialect":"MSA", ...},
 {"original_text":"وين تروح؟","normalized_text":"وين تروح?","dialect":"GLF", ...}]}
```

`texts` must be a non-empty list of strings; `batch_size` and `workers` are
optional positive integers.

### Error mapping

Every failure is a JSON error object —
`{"schema_version":1,"error":{"code":"...","message":"..."}}` — with a
stable HTTP status:

| Status | Code | Trigger (verified) |
|--------|------|--------------------|
| `400` | `invalid_json` | Body is not valid UTF-8 JSON. |
| `400` | `invalid_payload` | Body is valid JSON but not an object. |
| `400` | `missing_text` | `/v1/normalize` without a `text` field. |
| `400` | `invalid_texts` / `empty_batch` | `/v1/batch` with a non-list, non-strings, or empty `texts`. |
| `400` | `invalid_stream_paths` | `/v1/stream` missing any of the three path strings. |
| `403` | `stream_path_forbidden` | A `/v1/stream` path resolves outside `--streaming-root`. |
| `404` | `not_found` | Unknown path or method. |
| `409` | `stream_conflict` | Another request/process holds the session lock. |
| `409` | `stream_source_changed` | Source mutated during the streamed run. |
| `411` | `length_required` | Missing/invalid `Content-Length`. |
| `413` | `request_too_large` | Body exceeds `--max-body-bytes`. |
| `415` | `unsupported_media_type` | `Content-Type` is not `application/json`. |
| `422` | `invalid_text` | Wrong input type, e.g. `{"text": 42}` → `text must be str, got int`. |
| `422` | `invalid_request` | Other invalid values (e.g. `batch_size: -1`), AraNorm `ValueError`/`TypeError`. |
| `500` | `internal_error` | Unexpected exception; details go to the server log, never the response. |

Error responses deliberately reveal no input text or stack traces — the
`500` body is a constant, and the exception is logged server-side.

### Health checks for orchestrators

Use the two probes for their intended purposes:

- **Liveness** (`GET /health/live`) — "is the process alive?" Wire to
  container/Kubernetes *liveness* probes and dead-peer detection; the
  response is constant, with no pipeline involvement.
- **Readiness** (`GET /health/ready`) — "can this instance serve traffic
  *correctly* right now?" Reports the runtime health snapshot: `status`
  (`ready`/`degraded`), `generation` (configs published so far),
  `config_fingerprint`, and `last_reload_error`.

Because a failed reload always preserves the last good pipeline snapshot, a
healthy AraNorm process keeps answering `/health/ready` with `200` even while
`status` is `degraded`. The `503` path exists for runtimes that genuinely
have no usable snapshot. Concretely:

| Probe behavior | Recommended consumer |
|----------------|----------------------|
| `/health/live` != 200 | Restart the process (crash/exit). |
| `/health/ready` returns 503 | Remove from rotation — no usable pipeline. |
| `/health/ready` returns 200 with `"status":"degraded"` | Page/alert: serving *stale config*; fix the config file (see [runbook](#operations-runbook)). |

A minimal watchdog loop:

```python
import json, time, urllib.request

while True:
    health = json.load(urllib.request.urlopen("http://127.0.0.1:8765/health/ready"))
    if health["status"] == "degraded":
        alert(health["last_reload_error"])   # {"error_type": ..., "message": ...}
    time.sleep(10)
```

### Graceful degradation

`RuntimeHealth` (returned by `PipelineRuntime.health()` and `/health/ready`)
models degradation explicitly: `status` is `"ready"` or `"degraded"`, and
`ready` reports whether a usable snapshot exists. After a failed reload,
`status` flips to `"degraded"`, `last_reload_error` is populated with bounded,
sanitized diagnostics (`{"error_type", "message"}` — no configuration
payloads, no input text), and — crucially — `process()`/`process_batch()` keep
using the **last good snapshot**. Degradation never stops serving; it only
signals that the running configuration is not the one you asked for.

---

## Level 3 — Configuration management

Long-lived services need configuration to be a *managed artifact*: versioned,
validated, and replaceable without downtime. AraNorm provides three layers.

### `PipelineConfig` files

`PipelineConfig.from_file(path)` loads a configuration from JSON
(`.json`) or YAML (`.yaml`/`.yml` — requires `pip install PyYAML`; the
library itself has zero mandatory dependencies). The JSON form is a flat
dictionary of the documented flags:

```json
{
  "preset": "standard",
  "remove_diacritics": true,
  "handle_arabizi": false,
  "clean_urls": true,
  "dialect_target": "none"
}
```

Field names are validated strictly — an unknown key is rejected with
`Unknown PipelineConfig field(s): <name>` rather than ignored, so typos in
production configs fail at load time, not silently at request time.

### `PipelineSpec` — portable, fingerprinted pipelines

A `PipelineSpec` is a *versioned envelope* around a config:
`schema_version`, `library_version`, `pipeline_class`, `config`,
`config_fingerprint`, and `metadata`. The fingerprint (SHA-256 over the
canonical config) lets you verify that a spec reconstructs the *exact*
pipeline that produced it:

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig, PipelineSpec

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))

spec = pipeline.to_spec(metadata={"environment": "production"})
spec.write_file("spec.json")              # atomic: temp file + fsync + rename

loaded = PipelineSpec.read_file("spec.json")   # strict, ≤ 1 MiB by default
rebuilt = loaded.to_pipeline()            # raises if fingerprint mismatch
```

Specs close the loop that raw configs leave open: a config says *what you
want*, a spec says *what you had* — including proof it rebuilds identically.
The CLI mirrors this workflow (`aranorm spec export`, `aranorm spec
validate`), and `aranorm serve --spec spec.json` boots a server from one.

### Snapshots

For auditing "what changed between two pipelines", `PipelineSnapshot`
captures config plus stage order and metadata, round-trips through JSON, and
diffs:

```python
from aranorm import PipelineConfig
from aranorm.core.snapshot import snapshot_pipeline, PipelineSnapshot

snap = snapshot_pipeline(PipelineConfig(preset="deep"), metadata={"env": "docs"})
snap.save("pipeline.snapshot.json")
PipelineSnapshot.load("pipeline.snapshot.json") == snap          # True
snap.diff(snapshot_pipeline(PipelineConfig(preset="standard")))   # non-empty
```

### Atomic hot reload

`PipelineRuntime` is the engine behind `aranorm serve`. It holds one
**published pipeline snapshot** behind a lock, and `reload()` follows a
build-then-swap protocol: the candidate config is cloned, validated, and
built into a complete pipeline *before* anything is published. Readers either
see the old snapshot or the new one — never a half-initialized pipeline.

```python
from aranorm import PipelineConfig, PipelineRuntime

runtime = PipelineRuntime(PipelineConfig(preset="standard"))
runtime.generation          # 0
runtime.process("السَّلامُ عَلَيْكُم").normalized_text   # "السلام عليكم"

result = runtime.reload(PipelineConfig.from_dict(
    {**runtime.config.to_dict(), "remove_diacritics": False}
))
result.success, result.generation          # True, 1

# a broken reload preserves the old snapshot and marks degraded
outcome = runtime.reload_from_spec({"schema_version": 1})
outcome.success, outcome.error_type        # False, "ConfigurationError"
runtime.health().status                    # "degraded"
runtime.process("مُحَمَّد")                # still served by generation 1
```

`ReloadResult.to_dict()` is JSON-ready for audit logs:

```json
{"schema_version": 1, "success": true, "generation": 1,
 "config_fingerprint": "2a6f7d1305793fa1481085c90deb94c2d40455ff078844f1332e6361a6b4b1e4",
 "error_type": null, "error_message": null}
```

Reload entry points: `reload(config)`, `reload_from_spec(spec)`,
`reload_from_spec_file(path)`, and `reload_from_file(path)` for JSON/YAML
config files. All follow the same build-then-swap protocol and return
`ReloadResult`.

**Wiring it to a live server.** `ConfigReloadWatcher` polls the config or
spec file's mtime on a daemon thread and applies changes through the atomic
path:

```python
from aranorm import PipelineConfig, PipelineRuntime
from aranorm.server import ConfigReloadWatcher, create_server

runtime = PipelineRuntime(PipelineConfig(preset="standard"))
watcher = ConfigReloadWatcher(runtime, "config.json", interval=2.0)
watcher.start()

server = create_server(runtime, "127.0.0.1", 8765)   # created, not started
try:
    server.serve_forever()
finally:
    watcher.stop()
    server.server_close()
```

The CLI does exactly this with `--config config.json --reload-interval 2.0`.
The watcher only reloads when mtime actually changes, logs successes at INFO
(`configuration reloaded at generation N`) and failures at ERROR, and never
restarts the process.

**A verified reload session**, from a live server started with
`--config reload-config.json --reload-interval 1.0`:

```console
$ curl -s http://127.0.0.1:8767/health/ready
{"status":"ready","generation":0,"config_fingerprint":"e5144fa...","last_reload_error":null}

# edit reload-config.json: "remove_diacritics": false … wait ≥ 1 s …

$ curl -s http://127.0.0.1:8767/health/ready
{"status":"ready","generation":1,"config_fingerprint":"2a6f7d1...","last_reload_error":null}

$ curl -s -X POST localhost:8767/v1/normalize -H "Content-Type: application/json" \
       -d '{"text":"مُحَمَّد يُسافِر غَداً"}' | jq -r .result.normalized_text
مُحَمَّد يُسافِر غَداً          # diacritics now preserved

# now break the file on purpose (an unknown field) …

$ curl -s http://127.0.0.1:8767/health/ready
{"status":"degraded","generation":1,"config_fingerprint":"2a6f7d1...",
 "last_reload_error":{"error_type":"ValueError",
                      "message":"Unknown PipelineConfig field(s): max_batch_size"}}

# … the server keeps serving generation 1 until the file is fixed, then:
{"status":"ready","generation":2,"last_reload_error":null}
```

Note what the degraded state did *not* do: stop serving, exit, or roll back to
generation 0 — it kept the **last valid snapshot** until a valid file
reappeared.

---

## Scaling

**What kind of server is this?** `ThreadingHTTPServer` spawns one thread per
connection, with `daemon_threads = True` so in-flight connections never block
shutdown, and `allow_reuse_address = True` for quick restarts. There is no
async event loop and no process pool: AraNorm's normalization work is pure
Python regex over CPU-bound text, so the GIL is the ceiling for a single
process. Threads buy you **I/O parallelism** (many slow clients, keep-alive
gaps, concurrent uploads), not CPU parallelism.

**Measured reference points** (single container core, standard preset, short
social-media-style Arabic sentences — treat as an upper bound, not an SLO):

| Path | Measurement |
|------|-------------|
| In-process `runtime.process()` | ≈ 2,400 items/s (0.42 ms/item) |
| In-process `process_batch()` (100/batch) | ≈ 2,600 items/s |
| HTTP `POST /v1/normalize`, sequential client | ≈ 845 req/s (1.18 ms/req) |
| HTTP `POST /v1/batch` (99 items/request) | ≈ 2,594 items/s (26 req/s) |

Reading the table:

- **Batch over single-item whenever latency allows** — the batch endpoint
  nearly matches in-process throughput; one-item HTTP requests pay ~40%
  overhead per item.
- **Horizontal scaling is the CPU answer** — one process saturates at roughly
  one core, so run N processes (one per core or per container) behind a load
  balancer; `allow_reuse_address` makes port re-binding safe across restarts.
- **`workers` helps modestly** — with GIL-bound regex work expect diminishing
  returns past 2–4; measure with `metrics_snapshot()` before committing.

Conservative capacity planning (plan at ~⅓ of measured peak):

| Target sustained rate | Deployment shape |
|-----------------------|------------------|
| ≤ 200 req/s single items | 1 instance, 1–2 vCPU, behind nginx |
| ≤ 2,000 items/s, batchable | 1–2 instances, batching clients at 50–100 items/request |
| > 5,000 items/s | N instances (1 vCPU each) behind a load balancer, batch endpoint, autoscale on CPU |

---

## Security hardening

The server has **no built-in authentication, TLS, or rate limiting**. That is
a design decision, not an omission: it is intended for local use or behind a
reverse proxy that owns those concerns. The threat model and mitigations:

- **Bind to localhost by default.** The default `--host 127.0.0.1` keeps the
  service unreachable from the network until you deliberately expose it.
- **Terminate TLS and auth at the proxy.** A minimal nginx front:

  ```nginx
  server {
      listen 443 ssl;
      server_name normalize.internal.example.com;
      ssl_certificate     /etc/ssl/certs/normalize.pem;
      ssl_certificate_key /etc/ssl/private/normalize.key;
      client_max_body_size 2m;              # match --max-body-bytes
      limit_req_zone $binary_remote_addr zone=aranorm:10m rate=50r/s;
      location / {
          limit_req zone=aranorm burst=100;
          proxy_pass http://127.0.0.1:8765;
          proxy_set_header Host $host;
      }
  }
  ```

- **Keep `--max-body-bytes` as low as your payloads allow.** The default
  2,000,000 bytes already bounds memory per request; a batching client that
  needs 100 sentences rarely needs more than a few hundred KB.
- **`/v1/stream` is disabled by default — keep it that way unless you need
  it.** When enabled, always set `--streaming-root` so requests cannot name
  arbitrary filesystem paths, remember that the endpoint forces session
  locking (concurrent duplicates get `409`), and prefer absolute paths
  (relative paths resolve against the server's working directory). See
  [streaming.md](streaming.md#http-triggered-sessions).
- **Error responses leak nothing.** Input text, configuration payloads, and
  tracebacks stay in server logs; clients receive stable codes and constant
  `500` bodies.
- **Never expose checklist:**
  - [ ] Service bound to `127.0.0.1`, only the proxy listens publicly.
  - [ ] TLS + authentication enforced at the proxy.
  - [ ] Rate limiting configured at the proxy.
  - [ ] `--max-body-bytes` sized to your real payloads.
  - [ ] `/v1/stream` off, or confined with `--streaming-root` on a directory
        containing nothing but streaming jobs.
  - [ ] Container runs as a non-root user with a read-only root filesystem
        (see [Docker recipe](#docker-recipe)).

---

## Docker recipe

AraNorm is a pure-Python, dependency-free wheel — the image is minimal:

```dockerfile
FROM python:3.12-slim

# Non-root runtime user
RUN useradd --create-home --shell /usr/sbin/nologin aranorm

WORKDIR /app

# Pin the version you validated
RUN pip install --no-cache-dir aranorm==1.15.0

COPY config.json /app/config.json

USER aranorm

EXPOSE 8765

# Probe /health/live with the stdlib (slim images have no curl)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/health/live', timeout=2).status==200 else 1)"

CMD ["aranorm", "serve", "--host", "0.0.0.0", "--port", "8765", \
     "--config", "/app/config.json", "--reload-interval", "2.0"]
```

Run it:

```console
$ docker build -t aranorm:1.15.0 .
$ docker run -d --name aranorm \
    -p 127.0.0.1:8765:8765 \
    -v $PWD/config.json:/app/config.json:ro \
    aranorm:1.15.0
```

Notes:

- `--host 0.0.0.0` inside the container is correct — the port mapping pins
  exposure to localhost on the host; put your proxy there.
- The mounted `config.json` plus `--reload-interval` gives you config rollout
  with `docker cp`/config-map updates and **no container restarts**.
- The `HEALTHCHECK` uses the verified stdlib one-liner; wire the same probe
  into Kubernetes `livenessProbe`/`readinessProbe` and alert on
  `"status":"degraded"` separately from restarts.
- Kubernetes pattern: a `Deployment` with one replica per core, probes on
  `/health/live` and `/health/ready`, config in a `ConfigMap` mounted at
  `/app/config.json`, HPA on CPU. No state lives in the container — every
  instance is interchangeable.

---

## Monitoring

Four observability surfaces, all JSON:

1. **Health polling.** `/health/ready` exposes `generation`,
   `config_fingerprint`, `status`, and `last_reload_error`. Alert rules:
   - `status == "degraded"` for > 5 minutes → config rollout is stuck; see
     the [runbook](#operations-runbook).
   - `generation` changed unexpectedly → someone reloaded the config; check
     audit logs.
   - `config_fingerprint` differs across instances behind one load balancer
     → config skew; instances are normalizing differently.

2. **Pipeline metrics.** `pipeline.metrics_snapshot()` (or
   `runtime.get_pipeline().metrics_snapshot()` when embedding) yields
   `total_items`, `succeeded`, `failed`, `total_time_ms`,
   `average_time_ms`, and `throughput_per_second` — scrapeable for
   latency/throughput dashboards. `to_json()` adds a stable
   `schema_version` envelope for machine consumers.

3. **Describe metadata.** `GET /v1/describe` (or `runtime.describe()`)
   returns the operational description — schema version, pipeline class,
   `config_fingerprint`, and full normalized config — plus a `runtime`
   section (`{"generation": N, "status": "ready"}`). Use it to verify *what*
   an instance is running, e.g. after a deploy.

4. **Request logs.** Access logs are emitted through the standard
   `aranorm.server` logger at INFO. The CLI does not configure logging, so
   enable it explicitly to capture requests (useful in containers):

   ```python
   # serve_app.py — a tiny wrapper for production logging
   import logging
   logging.basicConfig(level=logging.INFO,
                       format="%(asctime)s %(levelname)s %(name)s %(message)s")
   from aranorm import PipelineConfig, PipelineRuntime
   from aranorm.server import serve

   serve(PipelineRuntime(PipelineConfig.from_file("config.json")), "127.0.0.1", 8765)
   ```

   ```text
   2026-11-27 19:36:59,914 INFO aranorm.server 127.0.0.1 - "POST /v1/normalize HTTP/1.1" 200 -
   ```

   Reload failures log at ERROR (`configuration reload failed: ...`) — route
   `aranorm.server` logs to your log aggregator and alert on ERROR.

For batch/CLI operations, prefer `--json` output (stable, `ensure_ascii=False`)
piped to `jq`, which keeps Arabic text readable and parsing deterministic.

---

## Operations runbook

| Symptom | Likely cause | Diagnosis | Recovery |
|---------|--------------|-----------|----------|
| `/health/ready` shows `"status":"degraded"` | Hot reload failed: config file is invalid (unknown field, bad type), missing, or unreadable | Read `last_reload_error` (`{"error_type","message"}`) and the server log's `configuration reload failed:` line | Fix or roll back the config file; the watcher picks up the new mtime automatically, publishes generation N+1, and `status` returns to `ready`. No restart needed. |
| Instances behind LB have different `config_fingerprint` | Config skew — some instances reloaded, others didn't (or from different files) | Compare `GET /v1/describe` across instances | Force a consistent rollout (redeploy config everywhere), then verify fingerprints match before returning traffic. |
| `Error: could not start server: … Address already in use` | Port conflict — previous instance still bound | `ss -ltnp \| grep 8765` | Stop the old process/container; `allow_reuse_address` already handles TIME_WAIT. Consider a systemd socket or orchestrator health-gated rollout. |
| `409 stream_conflict` from `/v1/stream` or `StreamingSessionConflictError` | Another process holds the `.lock` for that checkpoint tuple | `aranorm stream status --checkpoint C`; check for a running owner | Wait for the owner to finish, or run the duplicate job with a new checkpoint tuple. Locks auto-release when owners die — no stale-lock surgery. |
| `CheckpointError` on resume | Source file, pipeline config, or paths changed since the checkpoint | `aranorm stream status --checkpoint C` and compare fingerprints | Restore the matching source/config to resume, or delete checkpoint + output to start fresh. Never hand-edit checkpoints. |
| `413 request_too_large` bursts in logs | Clients exceeding `--max-body-bytes` | Check client batch sizes vs the limit | Split client batches or raise `--max-body-bytes` (and the proxy's `client_max_body_size`) together. |
| Latency creeping up, memory growing | Cache pressure or oversized texts | `NormalizationCache.stats()`, `metrics_snapshot().average_time_ms`, input length distribution | Resize/`clear()` the cache; cap input length upstream; scale horizontally (see [Scaling](#scaling)). |
| Process restarted (liveness failing) | Crash or OOM — not a config issue (config failures never exit the process) | Container exit code, OOM events, `aranorm.server` logs | Address the resource cause; bump memory/CPU limits; verify with `/health/live` probes. |

Two invariants worth memorizing for incidents: **a bad config never stops
serving** (last good snapshot wins, degraded flag raised), and **a killed
streaming job never loses committed work** (resume from the checkpoint). Most
"AraNorm is down" incidents turn out to be proxy, DNS, or capacity issues in
front of a still-healthy process — check `/health/live` on the instance
itself first.

---

*See also: [streaming.md](streaming.md) for resumable streaming sessions,
[cli.md](cli.md) for the complete command reference, and the project
README for library-level quick starts.*
