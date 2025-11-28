#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright
import json

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
BASE = "http://localhost:8080"
OUTPUT = Path("logs/css_coverage_summary.json")

EVAL_SCRIPT = """
(() => {
  const summary = {};
  for (const sheet of Array.from(document.styleSheets)) {
    const href = sheet.href || '';
    if (!href.includes('/web/assets/')) continue;
    if (!summary[href]) summary[href] = { total: 0, used: 0 };
    const bucket = summary[href];
    let rules;
    try {
      rules = Array.from(sheet.cssRules || []);
    } catch (err) {
      continue;
    }
    for (const rule of rules) {
      if (!rule.selectorText) continue;
      bucket.total += 1;
      const selectors = rule.selectorText.split(',');
      let ruleUsed = false;
      for (const selector of selectors) {
        const trimmed = selector.trim();
        if (!trimmed) continue;
        try {
          if (document.querySelector(trimmed)) {
            ruleUsed = true;
            break;
          }
        } catch (err) {
          continue;
        }
      }
      if (ruleUsed) {
        bucket.used += 1;
      }
    }
  }
  return summary;
})()
"""


def normalize_url(source_url: str) -> str | None:
    if not source_url:
        return None
    if source_url.startswith(BASE):
        return source_url[len(BASE) :]
    return None


def collect():
    stats: dict[str, dict[str, int]] = {}
    failed: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-gpu"])
        context = browser.new_context()
        for path in URLS:
            url = BASE + path
            page = context.new_page()
            print(f"[coverage] visiting {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(500)
                page_data = page.evaluate(EVAL_SCRIPT)
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{url}: {exc}")
                page_data = {}
            finally:
                page.close()
            for href, data in page_data.items():
                rel = normalize_url(href)
                if not rel:
                    continue
                bucket = stats.setdefault(rel, {"total": 0, "used": 0})
                bucket["total"] += data.get("total", 0)
                bucket["used"] += data.get("used", 0)
        browser.close()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"coverage": stats, "failed": failed}, indent=2))
    return stats, failed


def main():
    stats, failed = collect()
    rows = []
    for rel, data in sorted(stats.items()):
        total = data["total"] or 1
        used = data["used"]
        unused = total - used
        pct = used / total * 100
        rows.append(
            {
                "stylesheet": rel,
                "rules_total": total,
                "rules_used": used,
                "rules_unused": unused,
                "usage_pct": round(pct, 1),
            }
        )
    summary = {"coverage": rows, "failed": failed}
    OUTPUT.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
