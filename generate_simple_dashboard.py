#!/usr/bin/env python3
"""
Regenerate docs/dashboard.html and docs/how-it-works.html from the issue
JSONs in docs/newsletters/ (stdlib only — no pipeline imports).

The dashboard used to be built here from ai_archive/ with a hard-coded
"$0.05" cost and "4 stories"; it now shows what each issue's `meta`
actually recorded. The pipeline writes the same pages when it publishes,
so this step is a refresh, not the only source.
"""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_site_pages():
    # Load the module by path: importing `src.publishers` would pull in the
    # whole pipeline (and its third-party dependencies).
    spec = importlib.util.spec_from_file_location(
        "site_pages", ROOT / "src" / "publishers" / "site_pages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    site_pages = _load_site_pages()
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    repo_url = os.getenv("GITHUB_REPO_URL", "https://github.com/eLh0m3r0/geodaily").rstrip("/")
    base_url = os.getenv("SITE_BASE_URL", "https://elh0m3r0.github.io/geodaily").rstrip("/")
    tagline = os.getenv("NEWSLETTER_TAGLINE", site_pages.DEFAULT_TAGLINE)
    dashboard = site_pages.build_dashboard_page(docs, repo_url=repo_url, tagline=tagline)
    pipeline = site_pages.build_pipeline_page(docs, repo_url=repo_url, site_base_url=base_url,
                                              tagline=tagline)
    print(f"Dashboard generated: {dashboard}")
    print(f"How-it-works page generated: {pipeline}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
