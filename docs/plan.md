# Plan: annotation counts per class

Branch `dev-test01`, forked from CVAT `develop` at `<<FILL: baseline SHA from git rev-parse HEAD before the first commit>>`.
Backend in a new Django app `cvat/apps/test`; UI as one new page in `cvat-ui`.

## Approach

- **Count in the database.** One `GROUP BY label` aggregate per annotation table that
  carries a label (shapes, tracks, tags, intervals), merged per label. Never load
  annotation objects into Python: COCO val2017 has ~37k instances and loading them
  scales with data size, an aggregate scales with the number of labels.
- **Reuse CVAT's login and IAM.** The endpoint asks the existing tasks OPA policy for
  `view:annotations`, the same decision `GET /api/tasks/{id}/annotations` uses.
  No new auth code, no new Rego.
- **Page state stays local to the page**, like the other task sub-pages
  (quality control, consensus); nothing goes into the Redux store.
- **Chart with the existing `chart.js` / `react-chartjs-2` dependencies.** No new package.

## Order of work and time budget (8 h)

Docker images and the COCO import run in the background first; that wait is not counted.

| # | Work | Items | Budget |
|---|------|-------|--------|
| 1 | Read the code: annotation models, how a shape stores its label, task → job path, IAM/OPA, ASGI, UI routing | - | 1:00 |
| 2 | Count query + endpoint + tests against a hand-counted task | 1 | 1:15 |
| 3 | Page, route, menu entry, chart, empty and error-with-retry states | 2, 3, 4 | 1:15 |
| 4 | Auth: tests and curl demos for no login (401), no access (403), access (200) | 5 | 0:30 |
| - | **Checkpoint: items 1-4 work end to end. Nothing after this starts before that.** | | |
| 5 | MO-1: write the objective, benchmark script, 5 runs, report | 6 | 0:45 |
| 6 | One grouping: per label **and source** (manual / file / auto ...) | 7 | 0:30 |
| 7 | Live updates over WebSocket, then reconnect with backoff | 8, 9 | 1:30 |
| 8 | Docs, Definition of Done evidence, decision record | 10 | 0:45 |
| | Buffer | | 0:30 |

Why group by source (item 7): it is the one split that says how much of a class a human
actually drew versus imported or auto-annotated, which is what a lead needs to judge a
dataset. It lives on every annotation table (`Annotation.source`), so it costs one extra
`GROUP BY` column and no join.

## Decided to skip

- Per-frame-range and per-job filters (one extra filter is the brief; source wins, see above).
- De-duplicating annotations in overlapping job segments (image tasks have overlap 0).
- Caching the counts: measure first (MO-1); add only if the target is missed.
- Project-wide counts, CSV export, i18n, Cypress end-to-end tests.
- WebSocket proxying in the webpack dev server (`yarn start`); the Docker stack is the target.

## Changes to plan

<<CONFIRM OR EDIT EACH LINE AS YOU WORK, AND ADD ANY OTHER DIVERGENCE WITH ITS REASON>>

- Benchmark logs in once and reuses the session cookie instead of HTTP Basic auth:
  Basic auth re-hashes the password (PBKDF2) on every request and would dominate the timing.
- The WebSocket handler re-runs the REST endpoint for each push instead of having its own
  query and permission code, so both paths can never disagree (see decision record).
- A table under the chart was added: the categorical colours for sources are below 3:1
  contrast, so the exact numbers must be readable without relying on colour.

## Decision record (item 10)

**Problem.** Item 8 needs the server to push when annotations change. CVAT runs Django
under uvicorn (ASGI), but Django's ASGI handler serves HTTP only, and CVAT has no
WebSocket or Channels code. Annotations are written both by the web process (editor
saves) and by RQ worker processes (imports), so an in-process signal cannot reach the
sockets on its own.

**Taken.** A small raw-ASGI WebSocket route wrapped around CVAT's existing ASGI
application (`cvat/asgi.py`), plus Redis pub/sub on CVAT's existing in-memory Redis.
Every annotation write ends in `task.touch()`; a `post_save` receiver on `Task`
publishes the task id after commit. Each socket subscribes to its task's channel and,
on a change, re-runs the real REST endpoint with the socket's own cookies, pushing the
full JSON snapshot. Login, IAM and the count query are therefore shared with HTTP.
No new dependency (uvicorn already ships `websockets`, `redis` is already installed).

**Rejected.** Django Channels with a Redis channel layer.

**What rejecting it cost.**
- About 80 lines of hand-written ASGI protocol handling (accept/close ordering, close
  codes, disconnect detection) that Channels' `AsyncWebsocketConsumer` gives for free.
- No Channels test tooling: the tests drive the ASGI callable with a hand-made fake socket.
- No "group" abstraction: every open socket holds its own Redis subscription and re-runs
  the count query on each change, so N viewers of one task cost N identical queries per
  save. Acceptable for a handful of viewers; it is the first thing to change at scale.
