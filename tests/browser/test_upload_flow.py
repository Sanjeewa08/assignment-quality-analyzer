import threading

import pytest
from werkzeug.serving import make_server


pytestmark = pytest.mark.browser


def test_register_upload_and_open_report_in_browser(app):
    from playwright.sync_api import Error, sync_playwright

    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except Error as exc:
                pytest.skip(f"Install the Playwright Chromium browser to run this UI test: {exc}")
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_port}/register")
            page.get_by_label("Email").fill("browser@example.test")
            page.get_by_label("Password").fill("browser-test-password")
            page.get_by_role("button", name="Create account").click()
            page.locator("#assignment").set_input_files({
                "name": "browser-assignment.txt",
                "mimeType": "text/plain",
                "buffer": b"Introduction\nA clear opening statement.\n\nAnalysis\nEvidence supports the claim.\n\nConclusion\nThe conclusion summarizes the evidence.",
            })
            page.get_by_role("button", name="Analyze assignment").click()
            page.get_by_role("heading", name="browser-assignment.txt").wait_for()
            assert page.get_by_text("OVERALL QUALITY SCORE").is_visible()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
