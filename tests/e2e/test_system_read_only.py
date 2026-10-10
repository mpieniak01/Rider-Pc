"""System pozwala obserwować usługi; kliknięcie nie zmienia robota."""


def test_cards_never_send_service_actions(browser_context):
    page, base_url = browser_context
    page.goto(base_url + "/system", wait_until="domcontentloaded")
    cards = page.locator(".service-node")
    cards.first.wait_for()
    before = len(page.requests)
    cards.first.click()
    page.wait_for_timeout(300)
    assert not [request for request in page.requests[before:] if request.method == "POST" and "/svc/" in request.url]
    assert cards.first.get_attribute("role") == "article"
    assert (
        "only" in cards.first.get_attribute("title").lower() or "odczyt" in cards.first.get_attribute("title").lower()
    )
    assert "demo" in cards.first.inner_text().lower()
