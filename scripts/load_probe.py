#!/usr/bin/env python3
"""Hit health and launch metadata only. Does not generate images."""

from __future__ import annotations

import argparse
import statistics
import time
import urllib.request


def timed(url: str) -> float:
    start = time.perf_counter()
    with urllib.request.urlopen(url, timeout=5) as response:
        response.read()
        if response.status >= 400:
            raise SystemExit(f"{url} -> {response.status}")
    return time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--n", type=int, default=25)
    args = parser.parse_args()
    samples = []
    for _ in range(args.n):
        samples.append(timed(f"{args.base}/health"))
        timed(f"{args.base}/v1/meta/launch")
    print(
        f"health_p50={statistics.median(samples):.4f}s "
        f"health_p95={sorted(samples)[max(0, int(len(samples)*0.95)-1)]:.4f}s n={len(samples)}"
    )


if __name__ == "__main__":
    main()
