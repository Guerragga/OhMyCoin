"""Check rendered desktop/mobile pages against the disposable Docker demo."""

from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    output = Path("browser-artifacts")
    output.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script("""window.cspErrors = [];
          document.addEventListener('securitypolicyviolation', event => {
            window.cspErrors.push(event.violatedDirective + ': ' + event.blockedURI);
          });""")
        page.goto("http://127.0.0.1:5000/login")
        page.locator('[name="email"]').fill("demo@example.com")
        page.locator('[name="password"]').fill("Demo@12345")
        page.locator('form[method="post"] button').click()
        page.wait_for_url("**/dashboard")
        paths = [
            "dashboard",
            "perfil",
            "configuracoes",
            "categorias",
            "contas",
            "movimentacoes",
            "previsoes",
            "cartoes",
            "dividas",
            "caixinhas",
        ]
        for width, label in [(1440, "desktop"), (390, "mobile")]:
            page.set_viewport_size({"width": width, "height": 1000})
            for path in paths:
                response = page.goto(f"http://127.0.0.1:5000/{path}", wait_until="networkidle")
                assert response.status == 200, path
                assert not page.evaluate("window.cspErrors"), (path, page.evaluate("window.cspErrors"))
                assert not errors, (path, errors)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), (
                    f"Horizontal page overflow: {path}/{label}"
                )
                if path == "dashboard":
                    assert page.evaluate("typeof Chart !== 'undefined'"), "Chart.js did not load"
                    assert page.locator("canvas").count() > 0
                    assert page.evaluate(
                        "Chart.getChart('chartContas').scales.y.ticks.some(t => t.label === 'Main Account')"
                    ), "Account chart must show category names, not currency values"
                    assert page.evaluate(
                        "Chart.getChart('chartCartoes').scales.y.ticks.some(t => t.label === 'Demo Card')"
                    ), "Card chart must show card names"
                page.screenshot(path=str(output / f"{path}-{label}.png"), full_page=True)
        # The confirmation must execute under the actual CSP and cancel the submit.
        page.goto("http://127.0.0.1:5000/categorias", wait_until="networkidle")
        dialogs = []

        def dismiss(dialog):
            dialogs.append(dialog.message)
            dialog.dismiss()

        page.on("dialog", dismiss)
        delete_button = page.locator("form[data-confirm] button").first
        delete_button.click()
        delete_button.click()
        assert len(dialogs) == 2, "Cancelled deletion must still prompt on the next attempt"
        browser.close()
    print("Desktop/mobile pages, charts, CSP and deletion confirmation passed.")


if __name__ == "__main__":
    main()
