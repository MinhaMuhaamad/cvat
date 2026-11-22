# Objectives

## MO-1: annotation counts response time

| ID | Field | Entry |
|----|-------|-------|
| MO-1 | What is measured | Wall-clock time of `GET /api/test/tasks/{id}/annotation-counts` (no grouping), from sending the request to receiving the last byte of the JSON body, as seen by an HTTP client on the same machine. |
| | How | `python cvat/apps/test/benchmark.py --task <id> --user <user>`: logs in once and reuses the session cookie, sends one warm-up request (discarded, printed), then 5 sequential requests timed with `time.perf_counter()`. Prints every run, the median and the spread (max - min). |
| | Target | Median of 5 runs at or below **150 ms**. |
| | Conditions | Local Docker stack from `docker compose up -d` (this branch's images), requests through Traefik at `http://localhost:8080`, one task holding the COCO 2017 val images and `instances_val2017.json` (counts below), default segment size, superuser account, no other CVAT activity, no other heavy program running. |
| | Not included | Rendering the chart in the browser, WebSocket push latency, the first request after a cold start (the warm-up is discarded), the `group_by=source` variant, tasks inside projects, tasks with overlapping segments. |

### Why 150 ms

- The page re-fetches on every live update, so the endpoint sits on the critical path of
  every change a viewer sees. Around 100 ms is the usual threshold for a response to feel
  immediate; the chart render comes on top of the API, so the API gets the larger share
  of a ~200 ms budget, not all of it.
- The work is one OPA policy call plus five SQL statements (four `GROUP BY label_id`
  aggregates over ~37k COCO instances, one label list). Aggregates like this run in tens
  of milliseconds on Postgres, so 150 ms is reachable, but only if nothing loads
  annotation rows into Python. CVAT's own `TaskAnnotation` path (used by export) does
  load every shape; using it would not meet this target. That comparison was reasoned,
  not measured.
- A number I can miss: if the stack runs on a laptop with Docker limited to a few CPUs,
  the OPA round trip and Traefik add real time. If the target is missed, the reason goes
  in the results below.

## Results

Data: `<<FILL: number of images>>` images, `<<FILL: total printed by the script>>` annotations, `<<FILL: labels printed by the script>>` labels, task id `<<FILL>>`.

Raw output, pasted unedited:

```text
<<FILL FROM MY MACHINE: full output of python cvat/apps/test/benchmark.py --task <id> --user <user>>>
```

| Run | Time (ms) |
|-----|-----------|
| 1 | `<<FILL>>` |
| 2 | `<<FILL>>` |
| 3 | `<<FILL>>` |
| 4 | `<<FILL>>` |
| 5 | `<<FILL>>` |
| **Median** | `<<FILL>>` |
| **Spread (max - min)** | `<<FILL>>` |

Verdict: `<<FILL: met / missed, and if missed, why>>`

### Query plan (only if the target is missed)

No index was added: the filter goes through the existing foreign-key index on
`job_id` of each annotation table. Before adding anything, look at the plans:

```bash
docker exec -it cvat_server bash -ic "python3 ~/manage.py shell -c \"
from django.db.models import Count
from cvat.apps.engine.models import Task
from cvat.apps.test.counts import _labelled_annotations
task = Task.objects.get(id=<id>)
for q in _labelled_annotations(task):
    print(q.values('label_id').annotate(n=Count('id')).order_by().explain(analyze=True))
\""
```

`<<FILL FROM MY MACHINE: plan output, only if you ran it>>`

## Machine

| | |
|---|---|
| CPU | `<<FILL>>` |
| RAM | `<<FILL>>` |
| Docker resources | `<<FILL: CPUs and memory given to Docker>>` |
| OS | `<<FILL>>` |
| CVAT commit cloned | `<<FILL>>` |

Commands that print these (PowerShell):

```powershell
(Get-CimInstance Win32_Processor).Name
"{0:N1} GB" -f ((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
docker info --format "{{.NCPU}} CPUs, {{.MemTotal}} bytes"
(Get-CimInstance Win32_OperatingSystem) | ForEach-Object { "$($_.Caption) $($_.Version)" }
git merge-base HEAD origin/develop
```
