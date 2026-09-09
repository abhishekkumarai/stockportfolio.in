"""Symbol master tests.

These read the checked-in app/data/nse_symbols.json — no network. They assert
on a handful of long-lived large caps rather than counts, so an index
reconstitution or a fresh master does not break the suite.
"""

import pytest

from app import symbols as S


@pytest.fixture(scope="module", autouse=True)
def require_master():
    if S.master.stats()["equities"] == 0:
        pytest.skip("symbol master not built; run python -m scripts.refresh_symbols")


@pytest.mark.parametrize(
    "probe",
    ["RELIANCE", "reliance", "  RELIANCE  ", "NSE:RELIANCE-EQ", "RELIANCE.NS", "INE002A01018"],
)
def test_every_namespace_resolves_to_the_same_record(probe):
    record = S.lookup(probe)
    assert record is not None
    assert record.symbol == "RELIANCE"


def test_translation_round_trip():
    assert S.to_fyers("RELIANCE") == "NSE:RELIANCE-EQ"
    assert S.to_yfinance("NSE:RELIANCE-EQ") == "RELIANCE.NS"
    assert S.to_tradingview("RELIANCE.NS") == "NSE:RELIANCE"
    assert S.to_screener("RELIANCE").endswith("/company/RELIANCE/")
    assert S.canonical("RELIANCE.NS") == "RELIANCE"


def test_unknown_symbol_returns_none_rather_than_raising():
    assert S.lookup("NOTAREALTICKER") is None
    assert S.lookup("") is None
    assert S.lookup("   ") is None
    assert S.to_fyers("NOTAREALTICKER") is None


def test_require_raises_for_unknown():
    assert S.master.require("SBIN").symbol == "SBIN"
    with pytest.raises(KeyError):
        S.master.require("NOTAREALTICKER")


def test_unknown_fyers_series_falls_back_to_bare_symbol():
    """A -XX series we do not carry should still resolve on the symbol itself."""
    assert S.lookup("NSE:RELIANCE-XX").symbol == "RELIANCE"


def test_records_carry_classification():
    record = S.lookup("RELIANCE")
    assert record.isin.startswith("INE")
    assert record.sector
    assert record.cap == "large"
    assert record.in_index("NIFTY50")
    assert record.fno is True
    assert record.lot_size >= 1


def test_benchmark_scales_with_cap():
    """A smallcap graded against the Nifty 50 measures size, not the stock."""
    assert S.master.benchmark_for("RELIANCE") == "NSE:NIFTY50-INDEX"

    smallcaps = S.universe(cap="small", limit=1)
    if smallcaps:
        assert S.master.benchmark_for(smallcaps[0].symbol) != "NSE:NIFTY50-INDEX"


def test_benchmark_for_unknown_symbol_still_returns_an_index():
    assert S.master.benchmark_for("NOTAREAL").startswith("NSE:")


def test_benchmark_ticker_lookup():
    assert S.master.benchmark_ticker("NIFTY50") == "NSE:NIFTY50-INDEX"
    assert S.master.benchmark_ticker("nifty50") == "NSE:NIFTY50-INDEX"
    assert S.master.benchmark_ticker("NOSUCHINDEX") is None


def test_search_requires_two_characters():
    assert S.search("R") == []
    assert S.search("") == []


def test_search_prefers_exact_symbol():
    assert S.search("INFY")[0].symbol == "INFY"


def test_search_ranks_larger_companies_first():
    """Typing "bajaj" should surface Bajaj Auto, not a namesake microcap."""
    results = S.search("bajaj", limit=5)
    assert results
    caps = [r.cap for r in results]
    assert caps[0] == "large"
    # Ordering must be non-decreasing in size rank.
    ranks = [S._CAP_RANK.get(c, 9) for c in caps]
    assert ranks == sorted(ranks)


def test_search_matches_company_name_not_only_ticker():
    assert any(r.symbol == "INFY" for r in S.search("infosys", limit=10))


def test_search_respects_limit():
    assert len(S.search("a", limit=3)) <= 3
    assert len(S.search("ta", limit=3)) <= 3


def test_universe_filters_are_conjunctive():
    nifty50 = S.universe(index="NIFTY50")
    assert len(nifty50) == 50
    assert all(r.in_index("NIFTY50") for r in nifty50)

    large_it = S.universe(sector="Information Technology", cap="large")
    assert all(r.cap == "large" and r.sector == "Information Technology" for r in large_it)
    assert {"INFY", "TCS"} <= {r.symbol for r in large_it}


def test_universe_index_filter_is_case_insensitive():
    assert len(S.universe(index="nifty50")) == len(S.universe(index="NIFTY50"))


def test_universe_fno_and_require_sector_filters():
    assert all(r.fno for r in S.universe(fno_only=True))
    assert all(r.sector for r in S.universe(require_sector=True, limit=50))


def test_universe_unfiltered_is_the_whole_market():
    assert len(S.universe()) > 1000


def test_universe_limit_and_sort_order():
    first_ten = S.universe(index="NIFTY50", limit=10)
    assert len(first_ten) == 10
    assert [r.symbol for r in first_ten] == sorted(r.symbol for r in first_ten)


def test_batched_respects_the_fyers_fifty_symbol_cap():
    records = S.universe(index="NIFTY500")
    batches = list(S.batched(records, size=50))
    assert all(len(b) <= 50 for b in batches)
    assert sum(len(b) for b in batches) == len(records)
    assert all(sym.startswith("NSE:") for sym in batches[0])


def test_batched_handles_empty_input():
    assert list(S.batched([])) == []


def test_sectors_are_unique_and_sorted():
    sectors = S.master.sectors()
    assert sectors == sorted(set(sectors))
    assert len(sectors) > 5
