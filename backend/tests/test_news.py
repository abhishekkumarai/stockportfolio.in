"""Unit tests for news tagging and taxonomy."""

from app.news import tag_headline


def test_tag_headline_governance():
    title = "SEBI issues show cause notice to company directors following auditor resignation"
    tag = tag_headline(title)
    assert tag == "Governance & Legal"


def test_tag_headline_earnings():
    title = "Tata Motors Q3 PAT surges 18% YoY with expanding EBITDA margins"
    tag = tag_headline(title)
    assert tag == "Earnings & Financials"


def test_tag_headline_order_win():
    title = "Larsen & Toubro secures mega offshore EPC order worth Rs 4500 crore"
    tag = tag_headline(title)
    assert tag == "Order Wins & Expansion"


def test_tag_headline_promoter():
    title = "Promoters increase share pledge to 28% for raising working capital"
    tag = tag_headline(title)
    assert tag == "Promoter & Insider"


def test_clean_fund_name():
    from app.news import clean_fund_name
    assert clean_fund_name("Parag Parikh Flexi Cap Fund - Direct Plan - Growth") == "Parag Parikh Flexi Cap Fund"
    assert clean_fund_name("HDFC Small Cap Fund - Growth Option - Direct Plan") == "HDFC Small Cap Fund"
    assert clean_fund_name("Axis Bluechip Fund (Direct) - IDCW") == "Axis Bluechip Fund"


def test_tag_headline_mutual_fund():
    assert tag_headline("Equity mutual funds record 22% surge in monthly inflows as SIP AUM touches record high") == "Earnings & Financials"
    assert tag_headline("AMCs announce revised TER and expense ratio limits for active mutual funds") == "Corporate Actions"
    assert tag_headline("Nippon India MF launches new multicap NFO targeting manufacturing theme") == "Order Wins & Expansion"


def test_portfolio_news_endpoint(monkeypatch):
    from starlette.testclient import TestClient
    from app.main import app

    # Mock fetch_free_ticker_news and fetch_free_fund_news so we don't hit external network
    import app.news as news_module
    monkeypatch.setattr(
        news_module,
        "fetch_free_ticker_news",
        lambda sym, limit=3: [
            {"symbol": sym, "title": f"{sym} Q3 profit surges", "tag": "Earnings & Financials", "impact": "BULLISH", "kind": "equity"}
        ],
    )
    monkeypatch.setattr(
        news_module,
        "fetch_free_fund_news",
        lambda scheme_code, scheme_name=None, limit=3: [
            {"symbol": "Parag Parikh Flexi Cap", "title": "Parag Parikh Flexi Cap AUM crosses milestone", "tag": "Earnings & Financials", "impact": "BULLISH", "kind": "fund", "scheme_code": scheme_code}
        ],
    )

    client = TestClient(app)
    payload = {
        "equity": [{"symbol": "TCS", "quantity": 10, "avg_cost": 3500}],
        "funds": [{"scheme_code": 122639, "units": 50, "avg_nav": 70, "scheme_name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"}],
        "cash": 0,
    }
    resp = client.post("/api/portfolio/news", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    symbols = [a["symbol"] for a in data["articles"]]
    assert "TCS" in symbols
    assert "Parag Parikh Flexi Cap" in symbols
