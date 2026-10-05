"""Real-browser review of the integrated Supervisor UI.

Drives headless Chromium against the running integrated frontend and the
integrated backend, over real HTTP, and reports what a reviewer needs to see:
the four coverage states rendered distinctly, no console errors, no broken
layout, and above all no claim anywhere that a professor was verified when none
was.

Read-only. Nothing is written and no production environment is contacted.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:5173/ScholarZone"
SHOTS = Path(r"C:\Users\GopaL\AppData\Local\Temp\kilo\review_shots")
SHOTS.mkdir(parents=True, exist_ok=True)

#: The four fixtures seeded by scripts/review_seed.py, and the copy that must
#: appear for each. This is the assertion that matters: the states must be told
#: apart, and none of them may imply a verified professor.
EXPECTATIONS = {
    1: ("verified", "Dr Ada Lovelace"),
    2: ("none verified", None),
    3: ("pending", None),
    4: ("rendering", None),
}

FORBIDDEN = [
    "verified professor",
    "professor verified",
    "guaranteed",
    "admission chance",
    "acceptance chance",
    "response rate",
    "success rate",
    "%",
]


async def main() -> None:
    report: dict = {"console_errors": [], "page_errors": [], "checks": [], "states": {}}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1000})
        page = await context.new_page()

        page.on(
            "console",
            lambda message: report["console_errors"].append(f"{message.type}: {message.text}")
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda exc: report["page_errors"].append(str(exc)))

        # ---- catalogue -------------------------------------------------
        await page.goto(f"{BASE}/scholarships", wait_until="networkidle")
        await page.wait_for_timeout(1200)
        body = await page.inner_text("body")
        report["checks"].append(("catalogue loads", "scholarship" in body.lower() or len(body) > 200))
        await page.screenshot(path=str(SHOTS / "01-catalogue.png"), full_page=True)

        card_label = await page.get_by_text("Potential Supervisors", exact=False).count()
        report["checks"].append(
            ("card CTA shows only for a verified count", card_label == 1)
        )

        # ---- each scholarship detail ------------------------------------
        for index, (state, expect_person) in EXPECTATIONS.items():
            await page.goto(f"{BASE}/scholarships/{index}", wait_until="networkidle")
            await page.wait_for_timeout(1500)
            text = await page.inner_text("body")
            lowered = text.lower()

            report["states"][index] = {
                "has_panel": "supervisor" in lowered,
                "has_professor": "Ada Lovelace" in text,
                "has_email": "a.lovelace@uni1.edu" in text,
                "has_no_email_instruction": "no verified email" in lowered,
                "has_not_published": "not published" in lowered,
                "snippet": text[:0],
            }

            hit = False
            for phrase in (
                "Dr Ada Lovelace",
                "No verified supervisors found yet",
                "has not been completed",
                "only after the page loads in a browser",
            ):
                if phrase.lower() in lowered:
                    hit = True
            report["states"][index]["state_rendered"] = hit
            report["states"][index]["matches_expectation"] = (
                report["states"][index]["has_professor"] == (expect_person is not None)
            )

            for forbidden in FORBIDDEN:
                if forbidden.lower() in lowered:
                    report["checks"].append(
                        (f"scholarship {index} must not claim '{forbidden}'", False)
                    )
            if expect_person is None and report["states"][index]["has_professor"]:
                report["checks"].append((f"scholarship {index} shows no phantom professor", False))

            await page.screenshot(path=str(SHOTS / f"02-detail-{index}.png"), full_page=True)

            # A broken layout shows up as content wider than the viewport.
            overflow = await page.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            report["checks"].append(
                (f"scholarship {index} has no horizontal overflow", overflow <= 1)
            )

        # ---- mobile -----------------------------------------------------
        mobile = await context.new_page()
        await mobile.set_viewport_size({"width": 360, "height": 780})
        await mobile.goto(f"{BASE}/scholarships/1", wait_until="networkidle")
        await mobile.wait_for_timeout(1500)
        mobile_overflow = await mobile.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        report["checks"].append(("360px view has no horizontal overflow", mobile_overflow <= 1))
        await mobile.screenshot(path=str(SHOTS / "03-mobile-360.png"), full_page=True)
        await mobile.close()

        # ---- supervised states are all distinct -------------------------
        snippets = {}
        for index in EXPECTATIONS:
            await page.goto(f"{BASE}/scholarships/{index}", wait_until="networkidle")
            await page.wait_for_timeout(1200)
            text = await page.inner_text("body")
            for phrase in (
                "Dr Ada Lovelace",
                "No verified supervisors found yet",
                "has not been completed",
                "only after the page loads in a browser",
            ):
                if phrase.lower() in text.lower():
                    snippets[index] = phrase
        report["checks"].append(
            ("each state renders a distinct message", len(set(snippets.values())) == 4)
        )

        await browser.close()

    report["state_phrases"] = snippets
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())