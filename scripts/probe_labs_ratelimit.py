"""Probe labs.limitlesstcg.com to find a safe request rate.

Hits a cheap endpoint (a known per-player decklist URL or the standings page)
at increasing RPM. Watches for 429s, slow responses, and Cloudflare blocks.
Reports the highest RPM that completed without throttling.

Usage:
    python scripts/probe_labs_ratelimit.py
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

import httpx

# A handful of cheap, real URLs to rotate through so we're not hammering one path.
# Real labs standings pages (cheap server-rendered HTML).
PROBE_URLS = [
    "https://labs.limitlesstcg.com/0065/standings",  # Campinas
    "https://labs.limitlesstcg.com/0064/standings",  # Utrecht
    "https://labs.limitlesstcg.com/0063/standings",  # Los Angeles
    "https://labs.limitlesstcg.com/0062/standings",  # Prague
]

USER_AGENT = "TrainerLab-Scout/1.0 (rate-limit-probe)"

# RPM levels to test in order. Each level runs for `BURST_SECONDS` seconds.
RPM_LEVELS = [240, 360, 480, 600]
BURST_SECONDS = 45


@dataclass
class Result:
    rpm: int
    sent: int
    ok: int
    rate_limited: int
    errors: int
    p50_ms: float
    p95_ms: float
    max_ms: float


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(round(p * (len(s) - 1))))
    return s[idx]


def probe(client: httpx.Client, rpm: int, seconds: int) -> Result:
    interval = 60.0 / rpm
    deadline = time.monotonic() + seconds
    sent = ok = rate_limited = errors = 0
    latencies: list[float] = []
    i = 0
    while time.monotonic() < deadline:
        url = PROBE_URLS[i % len(PROBE_URLS)]
        i += 1
        start = time.monotonic()
        try:
            r = client.get(url)
            dt_ms = (time.monotonic() - start) * 1000.0
            latencies.append(dt_ms)
            sent += 1
            if r.status_code == 200:
                ok += 1
            elif r.status_code in (429, 503):
                rate_limited += 1
                # back off a little so we don't get IP-banned
                time.sleep(2.0)
            else:
                errors += 1
        except httpx.HTTPError as exc:
            errors += 1
            sent += 1
            print(f"  ! network error: {exc}", file=sys.stderr)
        next_t = start + interval
        sleep_for = next_t - time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)
    return Result(
        rpm=rpm,
        sent=sent,
        ok=ok,
        rate_limited=rate_limited,
        errors=errors,
        p50_ms=percentile(latencies, 0.50),
        p95_ms=percentile(latencies, 0.95),
        max_ms=max(latencies) if latencies else 0.0,
    )


def main() -> int:
    print(f"probe target: limitlesstcg.com  (burst {BURST_SECONDS}s per level)")
    print(f"levels: {RPM_LEVELS}")
    print()
    print(
        f"{'rpm':>5} {'sent':>5} {'ok':>4} {'429/503':>8} {'err':>4} "
        f"{'p50_ms':>8} {'p95_ms':>8} {'max_ms':>8}  verdict"
    )
    safe_max = 0
    with httpx.Client(
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for rpm in RPM_LEVELS:
            r = probe(client, rpm, BURST_SECONDS)
            verdict = "ok" if r.rate_limited == 0 and r.errors == 0 else "throttled"
            print(
                f"{r.rpm:>5} {r.sent:>5} {r.ok:>4} {r.rate_limited:>8} {r.errors:>4} "
                f"{r.p50_ms:>8.0f} {r.p95_ms:>8.0f} {r.max_ms:>8.0f}  {verdict}"
            )
            if verdict == "ok":
                safe_max = r.rpm
            else:
                print()
                print(f"  -> stopping at first throttle; highest clean RPM = {safe_max}")
                break
            time.sleep(5.0)  # cooldown between levels
    print()
    print(f"recommended LABS_REQUESTS_PER_MINUTE = {safe_max}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
