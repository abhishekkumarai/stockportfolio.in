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
