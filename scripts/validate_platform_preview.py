"""Exercise the real demo build at an explicit URL; never infer external readiness.

Requires Playwright Python and Chromium. Output/screenshots belong outside Git.
--local-canary verifies zero upstream calls when Next's BACKEND_URL points at 4011.
"""
import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


async def validate(args):
    target = args.url.rstrip("/")
    parsed = urlsplit(target)
    assert parsed.scheme in {"https", "http"} and parsed.hostname
    local = parsed.hostname in {"127.0.0.1", "localhost"}
    assert parsed.scheme == "https" or local, "Use HTTPS for an external preview"
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    upstream = []
    server = None
    if args.local_canary:
        assert local, "The upstream canary only establishes local isolation"

        class Canary(BaseHTTPRequestHandler):
            def handle_request(self):
                upstream.append(self.command)
                self.send_response(599)
                self.end_headers()

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = handle_request

            def log_message(self, *unused):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 4011), Canary)
        threading.Thread(target=server.serve_forever, daemon=True).start()

    result = {"url": target, "scope": "LOCAL_ONLY" if local else "EXTERNAL_HTTPS",
              "mode": "DEMO", "routes": [], "interactions": [], "failures": []}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=args.chromium, headless=True,
                                               args=["--no-sandbox"])
            context = await browser.new_context()
            page = await context.new_page()
            errors, failed_assets, browser_api, cancelled_prefetch = [], [], [], []
            def request_failed(request):
                # Next cancels speculative RSC prefetches when navigation changes.
                # Keep these separate; missing scripts/styles/fonts still fail.
                if request.failure == "net::ERR_ABORTED" and "_rsc=" in request.url:
                    cancelled_prefetch.append(request.url)
                else:
                    failed_assets.append({"url": request.url, "error": request.failure})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("response", lambda r: failed_assets.append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
            page.on("requestfailed", request_failed)
            page.on("request", lambda r: browser_api.append(r.url) if "/api/" in r.url else None)
            for viewport, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844)]:
                await page.set_viewport_size({"width": width, "height": height})
                for route in ["/", "/workspace", "/library", "/chat", "/credits"]:
                    response = await page.goto(target + route, wait_until="networkidle")
                    assert response.status == 200, (route, response.status)
                    await page.get_by_role("note").filter(has_text="Demo Preview").wait_for()
                    await page.evaluate("document.fonts.ready")
                    state = await page.evaluate("""() => ({
                        lang:document.documentElement.lang, dir:document.documentElement.dir,
                        dark:document.documentElement.classList.contains('dark'),
                        fonts:document.fonts.status,
                        main:document.querySelector('main').getBoundingClientRect().width,
                        width:innerWidth
                    })""")
                    assert state["lang"] == "ar" and state["dir"] == "rtl" and state["dark"]
                    assert state["fonts"] == "loaded"
                    assert state["main"] >= (width - 1 if viewport == "mobile" else 900), state
                    await page.screenshot(path=str(output / f"{viewport}-{route.strip('/') or 'home'}.png"), full_page=True)
                    refreshed = await page.reload(wait_until="networkidle")
                    assert refreshed.status == 200
                    result["routes"].append({"viewport": viewport, "route": route, "status": "PASS", "refresh": "PASS"})
                await page.locator('nav a[href="/workspace"]').first.click()
                await page.get_by_role("button", name="عرض مسودّة خيالية").click()
                await page.get_by_text("مثال خيالي ثابت — غير معتمد قانونياً", exact=True).wait_for()
                assert await page.get_by_role("button", name="نسخ المستند", exact=True).is_disabled()
                assert await page.locator("textarea").first.get_attribute("readonly") is not None
                await page.get_by_text("مثال خيالي ثابت — غير معتمد قانونياً", exact=True).scroll_into_view_if_needed()
                await page.screenshot(path=str(output / f"{viewport}-workspace-result.png"), full_page=True)
                result["interactions"].append(f"{viewport}: fixed draft, no approval, copy disabled")

                await page.locator('nav a[href="/library"]').first.click()
                await page.get_by_text("عقد تعاون خيالي — للعرض فقط", exact=True).click()
                await page.get_by_role("button", name="نسخ النصّ", exact=True).wait_for()
                assert await page.get_by_role("button", name="نسخ النصّ", exact=True).is_disabled()
                await page.screenshot(path=str(output / f"{viewport}-library-document.png"), full_page=True)
                await page.get_by_role("button", name="أغلق اللوحة", exact=True).click()
                await page.get_by_role("button", name="المقاطع", exact=True).click()
                await page.get_by_text("سجل مرجعي خيالي — ليس تشريعاً", exact=True).first.wait_for()
                result["interactions"].append(f"{viewport}: library, document panel, chunks, copy disabled")

                await page.locator('nav a[href="/chat"]').first.click()
                await page.get_by_role("button", name="أرسل السؤال", exact=True).click()
                await page.get_by_text("Demo Preview — إجابة خيالية ثابتة", exact=False).wait_for()
                result["interactions"].append(f"{viewport}: fixed chat, no verified citations")
                await page.locator('nav a[href="/"]').first.click()
                await page.get_by_role("heading", name="ابدأ الصياغة", exact=True).wait_for()

            assert not errors, errors
            assert not failed_assets, failed_assets
            assert not browser_api, browser_api
            result.update(console_errors=errors, failed_assets=failed_assets, browser_api_requests=browser_api,
                          cancelled_navigation_prefetches=len(cancelled_prefetch))

            # Probe the actual server boundary independently of the in-browser fixtures.
            api = context.request
            for method in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]:
                for route in ["revisions", "archive/upload", "archive/documents/private", "export", "analyze/clauses"]:
                    response = await api.fetch(f"{target}/api/{route}", method=method, data="sensitive-canary-do-not-reflect")
                    assert response.status == 403, (method, route, response.status)
                    assert "sensitive-canary" not in await response.text()
            for route in ["generate", "chat"]:
                response = await api.post(f"{target}/api/{route}", data="sensitive-canary-do-not-reflect")
                assert response.ok and response.headers["x-legal-brain-mode"] == "demo"
                assert "sensitive-canary" not in await response.text()
            response = await api.get(f"{target}/api/archive/documents?search=لا-يوجد")
            assert (await response.json())["documents"] == []
            response = await api.get(f"{target}/api/archive/chunks?family=contracts&limit=1")
            payload = await response.json()
            assert len(payload["chunks"]) == 1 and payload["chunks"][0]["family"] == "contracts" and payload["truncated"]
            result["api_boundary"] = {"denied_operations": 30, "fixed_sample_operations": 2, "filters": "PASS"}
            await browser.close()
        if server:
            assert upstream == [], upstream
            result["local_upstream_canary_requests"] = 0
        result["status"] = "PASS"
    except Exception as error:
        result["status"] = "FAIL"
        result["failures"].append(str(error))
        raise
    finally:
        if server:
            server.shutdown()
            server.server_close()
        (output / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    parser.add_argument("--local-canary", action="store_true")
    asyncio.run(validate(parser.parse_args()))
