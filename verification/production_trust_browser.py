"""Browser check of the verification badge on live production.

The API reports ``verification_status`` correctly; what matters to an applicant
is what the page says. These records are the hard cases:

* 140, 113, 79, 134 - the unresolved records, which must never read "Verified";
* an ordinary active record, which must.

A page that renders both "Verified listing" and "Needs review" is making two
contradictory claims at once, so that combination is treated as a failure rather
than as two correct labels.
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://scholarzone-fwzj.vercel.app"
NEEDS_REVIEW = (140, 113, 79, 134)
ACTIVE = (16, 1, 2)


def classify(text: str) -> dict:
    return {
        "render_error": "couldn’t be loaded" in text or "couldn't be loaded" in text,
        "verified": "Verified listing" in text,
        "confirm": "Confirm with provider" in text,
        "needs_review": "Needs review" in text,
        "chars": len(text),
    }


def main() -> None:
    results = []
    failures = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1024})
        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        for sid in list(NEEDS_REVIEW) + list(ACTIVE):
            page.goto(f"{BASE}/scholarships/{sid}", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_function(
                "() => !document.querySelector('[aria-busy=\"true\"]')"
                " && document.body.innerText.length > 800",
                timeout=45000,
            )
            text = page.inner_text("body")
            verdict = classify(text)
            heading = page.eval_on_selector("h1", "el => el.innerText.trim()")
            expects_review = sid in NEEDS_REVIEW

            problems = []
            if verdict["render_error"]:
                problems.append("page rendered the load-error state")
            if expects_review and verdict["verified"]:
                problems.append("a needs_review record renders a Verified claim")
            if expects_review and not verdict["confirm"]:
                problems.append("a needs_review record does not say Confirm with provider")
            if not expects_review and not verdict["verified"]:
                problems.append("an active record does not render as verified")
            if verdict["verified"] and verdict["confirm"]:
                problems.append("renders both Verified and Confirm at once")
            if verdict["verified"] and verdict["needs_review"]:
                problems.append("renders Verified and Needs review at once")

            results.append({"id": sid, "heading": heading, "expects_review": expects_review, **verdict})
            status = "FAIL" if problems else "ok"
            print(
                f"  {status:4s} id {sid:4d} verified={verdict['verified']!s:5s} "
                f"confirm={verdict['confirm']!s:5s} needs_review={verdict['needs_review']!s:5s} "
                f"chars={verdict['chars']:5d}  {heading[:44]}"
            )
            for problem in problems:
                print(f"        - {problem}")
                failures.append({"id": sid, "problem": problem})

        # The card badge in the directory: a hidden badge is a missing disclosure.
        page.goto(f"{BASE}/scholarships", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function(
            "() => document.body.innerText.length > 1500", timeout=45000
        )
        listing = page.inner_text("body")
        card_badges = {
            "confirm_with_provider": listing.count("Confirm with provider"),
            "verified_official_source": listing.count("Verified official source"),
        }
        print(f"\n  directory page: {card_badges}")
        if card_badges["confirm_with_provider"] == 0 and card_badges["verified_official_source"] == 0:
            failures.append({"id": "directory", "problem": "no card verification badge is rendered"})
            print("  FAIL directory publishes no card verification badge")

        browser.close()

    print(f"\napplication console errors: {len([e for e in console_errors if 'Failed to load resource' not in e])}")
    print(f"trust failures            : {len(failures)}")
    Path("verification/production_trust_browser.json").write_text(
        json.dumps(
            {
                "base": BASE,
                "records": results,
                "directory_card_badges": card_badges,
                "failures": failures,
                "console_errors": console_errors[:10],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print("wrote verification/production_trust_browser.json")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()