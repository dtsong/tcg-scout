#!/usr/bin/env python3
"""Discover API endpoints backing players.pokemon-card.com/event/result/list.

Uses Kernel.sh cloud browser + Playwright to intercept all XHR/fetch requests
made by the Vue.js SPA. Captures URLs, params, and response payloads.

Usage:
    python scripts/discover_result_list_api.py
"""

import asyncio
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv()

TARGET_URL = "https://players.pokemon-card.com/event/result/list"
RELEVANT_HOST = "players.pokemon-card.com"

# Skip static assets, analytics, etc.
SKIP_EXTENSIONS = {".js", ".css", ".png", ".jpg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf"}
SKIP_HOSTS = {
    "www.googletagmanager.com",
    "www.google-analytics.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
}


async def main():
    from kernel import Kernel
    from playwright.async_api import async_playwright

    api_key = os.environ.get("KERNEL_API_KEY", "")
    if not api_key:
        print("ERROR: KERNEL_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    kernel = Kernel(api_key=api_key)
    kb = kernel.browsers.create()
    captured = []

    print(f"Browser session: {kb.session_id}")
    print(f"Navigating to: {TARGET_URL}\n")

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
            context = browser.contexts[0]
            page = context.pages[0]

            async def on_response(response):
                url = response.url
                parsed = urlparse(url)

                # Skip irrelevant requests
                if parsed.hostname in SKIP_HOSTS:
                    return
                if any(url.endswith(ext) for ext in SKIP_EXTENSIONS):
                    return

                entry = {
                    "url": url,
                    "path": parsed.path,
                    "method": response.request.method,
                    "status": response.status,
                    "params": parse_qs(parsed.query),
                    "body": None,
                }

                # Try to capture JSON response body
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or "javascript" not in content_type:
                    try:
                        body = await response.json()
                        entry["body"] = body
                    except Exception:
                        try:
                            text = await response.text()
                            if len(text) < 5000:
                                entry["body"] = text[:2000]
                        except Exception:
                            pass

                captured.append(entry)

            page.on("response", on_response)

            # Phase 1: Initial page load
            print("=== Phase 1: Initial page load ===")
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            print(f"  Page title: {await page.title()}")
            print(f"  Captured {len(captured)} responses so far\n")

            # Phase 2: Look for filter controls and interact with them
            print("=== Phase 2: Exploring page controls ===")

            # Check what's on the page
            page_text = await page.evaluate("() => document.body.innerText.substring(0, 3000)")
            print(f"  Page text (first 500 chars):\n  {page_text[:500]}\n")

            # Look for select/dropdown elements
            selects = await page.query_selector_all("select")
            print(f"  Found {len(selects)} <select> elements")
            for i, sel in enumerate(selects):
                options = await sel.evaluate(
                    "el => Array.from(el.options).map(o => ({value: o.value, text: o.textContent.trim()}))"
                )
                print(f"    Select #{i}: {json.dumps(options, ensure_ascii=False)}")

            # Look for buttons/links that might be filters or pagination
            buttons = await page.query_selector_all("button, .btn, [role='button']")
            print(f"  Found {len(buttons)} button-like elements")
            for i, btn in enumerate(buttons[:10]):
                text = await btn.text_content()
                if text and text.strip():
                    print(f"    Button #{i}: {text.strip()[:80]}")

            # Look for any tab or filter UI
            tabs = await page.query_selector_all("[role='tab'], .tab, .nav-tab")
            print(f"  Found {len(tabs)} tab elements")

            # Phase 3: Try clicking filter options to trigger new API calls
            print("\n=== Phase 3: Triggering filter changes ===")
            pre_count = len(captured)

            # Try interacting with selects
            for i, sel in enumerate(selects[:3]):
                options = await sel.evaluate("el => Array.from(el.options).map(o => o.value)")
                for opt_val in options[1:3]:  # Try first 2 non-default options
                    await sel.select_option(opt_val)
                    await asyncio.sleep(2)
                    new_count = len(captured) - pre_count
                    if new_count > 0:
                        print(f"  Select #{i} -> '{opt_val}': triggered {new_count} new requests")
                        pre_count = len(captured)

            # Try clicking pagination if present
            next_btns = await page.query_selector_all(
                "text=次のページ, text=次へ, .next, [aria-label='next']"
            )
            if next_btns:
                print(f"  Found {len(next_btns)} pagination elements, clicking first...")
                await next_btns[0].click()
                await asyncio.sleep(2)
                new_count = len(captured) - pre_count
                print(f"  Pagination click triggered {new_count} new requests")

            await browser.close()
    finally:
        kernel.browsers.delete_by_id(kb.session_id)

    # Print summary
    print("\n" + "=" * 80)
    print("CAPTURED API CALLS")
    print("=" * 80)

    # Group by path
    api_calls = [c for c in captured if RELEVANT_HOST in c["url"]]
    other_calls = [c for c in captured if RELEVANT_HOST not in c["url"]]

    print(f"\n--- {RELEVANT_HOST} requests ({len(api_calls)}) ---\n")
    for i, call in enumerate(api_calls):
        print(f"[{i + 1}] {call['method']} {call['path']}")
        print(f"    Status: {call['status']}")
        if call["params"]:
            print(f"    Params: {json.dumps(call['params'], ensure_ascii=False)}")
        if call["body"]:
            body_str = json.dumps(call["body"], ensure_ascii=False, indent=2)
            # Truncate large responses
            if len(body_str) > 2000:
                body_str = body_str[:2000] + "\n    ... (truncated)"
            print(f"    Response:\n    {body_str}")
        print()

    if other_calls:
        print(f"\n--- Other requests ({len(other_calls)}) ---\n")
        for call in other_calls[:10]:
            parsed = urlparse(call["url"])
            print(f"  {call['method']} {parsed.hostname}{parsed.path} [{call['status']}]")


if __name__ == "__main__":
    asyncio.run(main())
