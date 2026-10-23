"""Optional real-browser audit of the self-contained evidence viewer; no model calls."""
import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent
AXE_SHA256 = "880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb"


def capture(output, axe_file):
    output.mkdir(parents=True, exist_ok=True)
    axe = axe_file.read_bytes()
    assert hashlib.sha256(axe).hexdigest() == AXE_SHA256
    errors, external, checks, audits, images = [], [], {}, {}, {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, width, height in (("desktop", 1440, 1000), ("mobile", 390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: external.append(r.url) if r.url.startswith(("http:", "https:")) else None)
            page.goto((DOCS / "release-review.html").as_uri())
            page.wait_for_selector(".task")
            configurations = page.evaluate("JSON.parse(document.getElementById('evidence').textContent).configurations")
            default_id = page.locator("#configuration").input_value()
            for config in configurations:
                page.select_option("#configuration", config["id"])
                expected = sum(t["row"]["task_success"] for t in config["tasks"])
                assert page.locator(".stat strong").first.inner_text() == f"{expected}/{len(config['tasks'])}"
                page.check("#failures")
                assert page.locator(".task").count() == len(config["tasks"]) - expected
                page.uncheck("#failures")
            page.select_option("#configuration", default_id)
            case = page.locator(".task").filter(has_text="original-incident").first
            if case.count():
                case.click()
            assert page.locator(".task[aria-pressed=true]").count() == 1
            selected_path = page.locator(".task[aria-pressed=true]").get_attribute("data-path")
            selected_config = next(c for c in configurations if c["id"] == default_id)
            expected_export = next(t["record"] for t in selected_config["tasks"] if t["path"] == selected_path)
            page.locator("#configuration").focus()
            page.keyboard.press("Tab")
            assert page.locator("#failures").evaluate("e=>e===document.activeElement")
            with page.expect_download() as download_info:
                page.get_by_role("button", name="Export displayed record").click()
            download = json.loads(Path(download_info.value.path()).read_text(encoding="utf8"))
            assert download == expected_export and "trace" in download and "evaluation" in download
            checks[name] = {"configuration_math": True, "failure_filter": True, "keyboard": True,
                            "record_export": True, "viewport": [width, height],
                            "no_overflow": page.evaluate("document.documentElement.scrollWidth<=innerWidth")}
            assert checks[name]["no_overflow"]
            # Inject the pinned local audit script, never load an external asset in the viewer.
            page.add_script_tag(content=axe.decode("utf8"))
            audit = page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
            audits[name] = {"violations": [{"id": r["id"], "impact": r["impact"], "description": r["description"]}
                                          for r in audit["violations"]],
                            "incomplete_rule_ids": [r["id"] for r in audit["incomplete"]],
                            "scope": "automated finite-page check, not accessibility certification"}
            assert not audits[name]["violations"], audits[name]
            page.evaluate("window.scrollTo(0,0)")
            image = output / f"release-review-{name}.png"
            page.screenshot(path=str(image), full_page=name == "mobile")
            images[image.name] = hashlib.sha256(image.read_bytes()).hexdigest()
            if name == "desktop":
                initial = next((c for c in configurations if c["id"] ==
                    "qwen3-v1/qwen3-14b-authority-facts-v4"), None)
                if initial:
                    page.select_option("#configuration", initial["id"])
                    page.check("#failures")
                    page.locator(".task").first.click()
                    assert page.locator("#detail").inner_text().startswith("TASK FAILED")
                    failure_audit = page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
                    assert not failure_audit["violations"]
                    audits["initial_failure"] = {"violations": [], "incomplete_rule_ids": [r["id"] for r in failure_audit["incomplete"]]}
                    page.evaluate("window.scrollTo(0,0)")
                    failed_image = output / "release-review-initial-failure.png"
                    page.screenshot(path=str(failed_image))
                    images[failed_image.name] = hashlib.sha256(failed_image.read_bytes()).hexdigest()
            page.close()
        browser.close()
    assert not errors and not external
    proof = {"captured_at": datetime.now(UTC).isoformat(), "source": "docs/release-review.html",
             "html_sha256": hashlib.sha256((DOCS / "release-review.html").read_bytes()).hexdigest(),
             "capture_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "axe_version": "4.10.3", "axe_sha256": AXE_SHA256, "checks": checks, "accessibility": audits,
             "page_errors": errors, "external_network_requests": external, "image_sha256": images,
             "execution_boundary": "actual Chromium rendering of recorded evidence; no fresh model or destination execution"}
    (output / "release-review-provenance.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf8", newline="\n")
    print(json.dumps({"browser_checks": checks, "page_errors": errors, "external_requests": external}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DOCS / "images/live-release")
    parser.add_argument("--axe-file", type=Path, required=True)
    args = parser.parse_args()
    capture(args.output, args.axe_file)
