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


def test_source_details_and_logs_stay_open_across_poll(browser_context):
    from playwright.sync_api import expect

    page, base_url = browser_context
    page.goto(base_url + "/system", wait_until="domcontentloaded")
    card = page.locator(".service-node").first
    card.wait_for()
    identity = card.get_attribute("data-identity")
    source = page.locator(f'[data-system-detail="source:{identity}"]')
    source.locator("summary").click()
    card.locator("[data-service-logs]").click()
    logs = page.locator(f'[data-system-detail="logs:{identity}"]')
    expect(logs).to_have_attribute("open", "")
    page.wait_for_timeout(5500)
    expect(source).to_have_attribute("open", "")
    expect(logs).to_have_attribute("open", "")
    logs.locator("summary").click()
    page.wait_for_timeout(5500)
    expect(logs).not_to_have_attribute("open", "")
    assert not [request for request in page.requests if request.method == "POST" and "/svc/" in request.url]


def test_provider_runtime_and_navigation_history_are_visible_read_only(browser_context):
    from playwright.sync_api import expect

    page, base_url = browser_context
    page.goto(base_url + "/control", wait_until="domcontentloaded")
    expect(page.locator("#provider-runtime")).to_contain_text("initialized=false")
    expect(page.locator("#provider-runtime")).to_contain_text("ready=false")
    assert any("/providers/capabilities" in request.url for request in page.requests)
    page.goto(base_url + "/navigation", wait_until="domcontentloaded")
    assert page.locator("#nav-request-history").count() == 1
    assert not page.errors
    assert not [request for request in page.requests if request.method == "POST" and "/api/navigator/" in request.url]
