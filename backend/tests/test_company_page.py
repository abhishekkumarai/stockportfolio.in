from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import company_page
from app.routes.stocks import router

# A trimmed copy of Screener's real markup: section ids, table classes, the
# trailing "+" on expandable rows, thousands separators, percent cells, blanks.
FIXTURE_HTML = """
<html><body>
<section id="quarters"><table class="data-table responsive-text-nowrap">
  <tr><th></th><th>Sep 2024</th><th>Dec 2024</th></tr>
  <tr><td>Sales&nbsp;+</td><td>64,259</td><td>63,973</td></tr>
  <tr><td>Net Profit +</td><td>11,909</td><td></td></tr>
</table></section>
<section id="profit-loss"><table class="data-table"><tr><th></th><th>Mar 2023</th><th>Mar 2024</th></tr>
  <tr><td>Sales +</td><td>2,25,458</td><td>2,40,893</td></tr></table>
  <table class="ranges-table"><tr><td>ignored</td></tr></table></section>
<section id="balance-sheet"><table class="data-table"><tr><th></th><th>Mar 2024</th></tr>
  <tr><td>Borrowings +</td><td>-</td></tr></table></section>
<section id="cash-flow"><table class="data-table"><tr><th></th><th>Mar 2024</th></tr>
  <tr><td>Cash from Investing Activity +</td><td>-1,807</td></tr></table></section>
<section id="shareholding">
  <div id="quarterly-shp"><table class="data-table"><tr><th></th><th>Sep 2024</th><th>Dec 2024</th></tr>
    <tr><td>Promoters +</td><td>71.77%</td><td>71.77%</td></tr>
    <tr><td>FIIs +</td><td>12.66%</td><td>12.10%</td></tr></table></div>
  <div id="yearly-shp" class="hidden"><table class="data-table"><tr><th></th><th>Mar 2024</th></tr>
    <tr><td>Promoters +</td><td>71.77%</td></tr></table></div>
</section>
</body></html>
"""


def test_parse_table_numbers_labels_and_blanks():
    page = company_page.parse_company_page(FIXTURE_HTML)
    q = page["quarterly_results"]
    assert q["periods"] == ["Sep 2024", "Dec 2024"]
    sales = q["rows"][0]
    assert sales["label"] == "Sales"  # trailing "+" and nbsp stripped
    assert sales["values"] == [64259.0, 63973.0]
    assert q["rows"][1]["values"] == [11909.0, None]  # blank cell is None, not 0


def test_indian_grouping_and_dash_cells():
    page = company_page.parse_company_page(FIXTURE_HTML)
    assert page["profit_loss"]["rows"][0]["values"] == [225458.0, 240893.0]
    assert page["balance_sheet"]["rows"][0]["values"] == [None]
    assert page["cash_flow"]["rows"][0]["values"] == [-1807.0]


def test_shareholding_percentages_both_views():
    sh = company_page.parse_company_page(FIXTURE_HTML)["shareholding"]
    assert sh["quarterly"]["rows"][1] == {"label": "FIIs", "values": [12.66, 12.1]}
    assert sh["yearly"]["periods"] == ["Mar 2024"]


def test_missing_sections_are_none_not_invented():
    page = company_page.parse_company_page("<html><body></body></html>")
    assert page["quarterly_results"] is None
    assert page["shareholding"] == {"quarterly": None, "yearly": None}


def _client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_financials_route_returns_sections():
    company_page._PAGE_CACHE.clear()
    with patch.object(company_page, "_fetch_html", return_value=FIXTURE_HTML):
        body = _client().get("/api/stocks/TCS/financials").json()
    assert body["available"] is True
    assert body["unit"] == "INR crore"
    assert body["profit_loss"]["periods"] == ["Mar 2023", "Mar 2024"]


def test_shareholding_route_returns_history():
    company_page._PAGE_CACHE.clear()
    with patch.object(company_page, "_fetch_html", return_value=FIXTURE_HTML):
        body = _client().get("/api/stocks/TCS/shareholding").json()
    assert body["available"] is True
    assert body["quarterly"]["rows"][0]["label"] == "Promoters"


def test_upstream_failure_is_unavailable_with_reason_and_not_cached():
    company_page._PAGE_CACHE.clear()
    with patch.object(company_page, "_fetch_html", side_effect=RuntimeError("Screener returned HTTP 403")):
        body = _client().get("/api/stocks/TCS/financials").json()
    assert body["available"] is False
    assert "403" in body["reason"]
    # A recovered upstream must be served on the very next request.
    with patch.object(company_page, "_fetch_html", return_value=FIXTURE_HTML):
        assert _client().get("/api/stocks/TCS/financials").json()["available"] is True
