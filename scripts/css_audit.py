#!/usr/bin/env python3
"""Capture screenshots i zestawienie użycia CSS."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.request
import re
from pathlib import Path

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
SUMMARY_JSON = Path("logs/css_audit_summary.json")
CSS_ROOT = Path("web")
CSS_FILES = sorted((CSS_ROOT / "assets").glob("*.css")) + sorted((CSS_ROOT / "assets" / "pages").glob("*.css"))
HTML_WHITELIST = Path("config/css_dynamic_whitelist.json")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
THEME = os.environ.get("CSS_AUDIT_THEME")

import uvicorn
from playwright.sync_api import Page, sync_playwright

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_server_thread(port: int) -> None:
    os.environ["TEST_MODE"] = "true"
    settings = Settings()
    cache = CacheManager()
    app = create_app(settings, cache)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def start_test_server() -> str:
    port = find_free_port()
    os.environ["TEST_SERVER_PORT"] = str(port)
    thread = threading.Thread(target=run_server_thread, args=(port,), daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            resp = urllib.request.urlopen(f"{base_url}/healthz", timeout=1)
            if resp.status == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError("Test server failed to start")
    return base_url


def collect_dom_tokens(page: Page) -> tuple[set[str], set[str]]:
    classes = set(
        page.eval_on_selector_all(
            "[class]",
            "els => Array.from(new Set(els.flatMap(el => (el.className||'').split(/\\s+/).filter(Boolean))))",
        )
        or []
    )
    ids = set(
        page.eval_on_selector_all(
            "[id]",
            "els => Array.from(new Set(els.map(el => el.id).filter(Boolean)))",
        )
        or []
    )
    return classes, ids


def perform_page_actions(page: Page, path: str) -> None:
    slug = path.split("/")[-1]
    try:
        if slug == "project.html":
            page.click("#new-task-btn", timeout=1000)
            page.wait_for_timeout(200)
        elif slug == "chat.html":
            page.fill("#input", "Audit ping", timeout=1000)
            page.click("#sendBtn", timeout=1000)
            page.wait_for_timeout(200)
    except Exception:
        # Page actions are optional enhancements; ignore failures from missing elements or timeouts
        pass


def take_screenshots(base_url: str) -> tuple[list[dict[str, str]], set[str], set[str]]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    shots: list[dict[str, str]] = []
    collected_classes: set[str] = set()
    collected_ids: set[str] = set()
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        if THEME:
            context.add_init_script(f"window.localStorage.setItem('dashboard_theme', {json.dumps(THEME)});")
        page = context.new_page()
        for path in URLS:
            slug = path.split("/")[-1].replace(".html", "") or "root"
            url = f"{base_url}{path}"
            print(f"[css:audit] visit {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            perform_page_actions(page, path)
            page.wait_for_timeout(500)
            classes, ids = collect_dom_tokens(page)
            collected_classes.update(classes)
            collected_ids.update(ids)
            outfile = LOG_DIR / f"{slug}.png"
            page.screenshot(path=str(outfile), full_page=True)
            shots.append({"url": url, "screenshot": str(outfile)})
        page.close()
        browser.close()
    return shots, collected_classes, collected_ids


def load_whitelist() -> tuple[set[str], set[str]]:
    classes: set[str] = set()
    ids: set[str] = set()
    if HTML_WHITELIST.exists():
        try:
            data = json.loads(HTML_WHITELIST.read_text())
            for cls in data.get("classes", []):
                for part in cls.split():
                    if part:
                        classes.add(part)
            for ident in data.get("ids", []):
                if ident:
                    ids.add(ident)
        except json.JSONDecodeError:
            print(f"[css:audit] warning: could not parse {HTML_WHITELIST}")
    return classes, ids


def calculate_css_usage(collected_classes: set[str], collected_ids: set[str]) -> list[dict]:
    class_whitelist, id_whitelist = load_whitelist()
    used_classes = collected_classes | class_whitelist
    used_ids = collected_ids | id_whitelist
    summary = []
    selector_re_class = re.compile(r"\.[A-Za-z0-9_-]+")
    selector_re_id = re.compile(r"#[A-Za-z0-9_-]+")
    for css in CSS_FILES:
        text = css.read_text(encoding="utf-8", errors="ignore")
        selectors = set(selector_re_class.findall(text) + selector_re_id.findall(text))
        class_total = 0
        class_hits = 0
        id_total = 0
        id_hits = 0
        for token in selectors:
            if token.startswith("."):
                class_total += 1
                if token[1:] in used_classes:
                    class_hits += 1
            elif token.startswith("#"):
                id_total += 1
                if token[1:] in used_ids:
                    id_hits += 1
        summary.append(
            {
                "stylesheet": str(css.relative_to(CSS_ROOT)),
                "class_selectors": class_total,
                "class_matched": class_hits,
                "id_selectors": id_total,
                "id_matched": id_hits,
            }
        )
    return summary


def main():
    base_url = start_test_server()
    screenshots, used_classes, used_ids = take_screenshots(base_url)
    usage = calculate_css_usage(used_classes, used_ids)
    SUMMARY_JSON.write_text(json.dumps({"screenshots": screenshots, "static_usage": usage}, indent=2))
    print(f"[css:audit] summary saved to {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
