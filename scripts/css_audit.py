#!/usr/bin/env python3
"""Capture screenshots i zestawienie użycia CSS."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8080"
URLS = [
    "/web/home.html",
    "/web/system.html",
    "/web/control.html",
    "/web/view.html",
    "/web/navigation.html",
    "/web/models.html",
    "/web/project.html",
    "/web/chat.html",
    "/web/google_home.html",
]
LOG_DIR = Path("logs/css_audit")
STATIC_USAGE_JSON = Path("logs/css_static_usage.json")
SUMMARY_JSON = Path("logs/css_audit_summary.json")
VENV_PYTHON = Path(".venv/bin/python").resolve()


def take_screenshots() -> list[dict[str, str]]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    shots: list[dict[str, str]] = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()
        for path in URLS:
            slug = path.split("/")[-1].replace(".html", "") or "root"
            url = f"{BASE_URL}{path}"
            print(f"[css:audit] visit {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(500)
            outfile = LOG_DIR / f"{slug}.png"
            page.screenshot(path=str(outfile), full_page=True)
            shots.append({"url": url, "screenshot": str(outfile)})
        page.close()
        browser.close()
    return shots


def run_static_usage() -> list:
    print("[css:audit] run css_static_usage.py")
    result = subprocess.run(
        [str(VENV_PYTHON), "scripts/css_static_usage.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(result.stdout.strip() or STATIC_USAGE_JSON.read_text())
    except json.JSONDecodeError:
        data = json.loads(STATIC_USAGE_JSON.read_text())
    return data


def main():
    screenshots = take_screenshots()
    usage = run_static_usage()
    SUMMARY_JSON.write_text(
        json.dumps(
            {
                "screenshots": screenshots,
                "static_usage": usage,
            },
            indent=2,
        )
    )
    print(f"[css:audit] summary saved to {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
