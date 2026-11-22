# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

"""
Measures MO-1: the response time of GET /api/test/tasks/{id}/annotation-counts.

Standard library only, so it runs from the host without a virtualenv:

    python cvat/apps/test/benchmark.py --task 1 --user admin

The password is read from CVAT_PASSWORD or asked for. The script logs in once and
reuses the session cookie, the same way the browser does. Basic auth is avoided on
purpose: it re-hashes the password on every request and would dominate the timing.
"""

import argparse
import getpass
import json
import os
import statistics
import time
import urllib.request
from http.cookiejar import CookieJar


def _login(opener: urllib.request.OpenerDirector, base_url: str, user: str, password: str) -> None:
    request = urllib.request.Request(
        f"{base_url}/api/auth/login",
        data=json.dumps({"username": user, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(request) as response:
        response.read()


def _timed_get(opener: urllib.request.OpenerDirector, url: str) -> tuple[float, int, dict]:
    started = time.perf_counter()
    with opener.open(url) as response:
        body = response.read()
        status = response.status
    elapsed_ms = (time.perf_counter() - started) * 1000
    return elapsed_ms, status, json.loads(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--url", default="http://localhost:8080", help="CVAT base URL")
    parser.add_argument("--task", type=int, required=True, help="Task id")
    parser.add_argument("--user", required=True, help="CVAT username")
    parser.add_argument("--group-by", choices=["source"], help="Benchmark the grouped variant")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    password = os.environ.get("CVAT_PASSWORD") or getpass.getpass(f"Password for {args.user}: ")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    _login(opener, args.url, args.user, password)

    url = f"{args.url}/api/test/tasks/{args.task}/annotation-counts"
    if args.group_by:
        url += f"?group_by={args.group_by}"

    print(f"GET {url}")
    warmup_ms, _, counts = _timed_get(opener, url)
    print(
        f"warm-up (discarded): {warmup_ms:.1f} ms, "
        f"total={counts['total']} annotations, labels={len(counts['labels'])}"
    )

    timings = []
    for run in range(1, args.runs + 1):
        elapsed_ms, status, counts = _timed_get(opener, url)
        timings.append(elapsed_ms)
        print(f"run {run}: {elapsed_ms:.1f} ms (HTTP {status}, total={counts['total']})")

    print(f"median: {statistics.median(timings):.1f} ms")
    print(f"spread: {max(timings) - min(timings):.1f} ms (min {min(timings):.1f}, max {max(timings):.1f})")


if __name__ == "__main__":
    main()
