"""Repo round-trips against a real (SQLite) database session."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db import repo
from app.schemas import EquityHolding, PortfolioRequest


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'test.db'}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def test_new_account_has_no_portfolio(session):
    # Regression: this used to raise ValidationError ("Portfolio must contain at
    # least one equity or fund holding") and surface as a 500 on
    # GET /api/accounts/me for every freshly created account.
    account, _key = repo.create_account(session, None, "empty")
    session.commit()
    assert repo.portfolio_for(session, account) is None


def test_portfolio_round_trips(session):
    account, _key = repo.create_account(session, None, "holder")
    session.commit()

    stored = repo.replace_holdings(
        session,
        account,
        PortfolioRequest(
            equity=[EquityHolding(symbol="RELIANCE", quantity=10, avg_cost=2500.0)]
        ),
    )
    session.commit()
    assert stored == 1

    portfolio = repo.portfolio_for(session, account)
    assert portfolio is not None
    assert [h.symbol for h in portfolio.equity] == ["RELIANCE"]
    assert portfolio.equity[0].quantity == 10


def test_replace_is_a_replacement_not_a_merge(session):
    account, key = repo.create_account(session, None, "holder")
    session.commit()

    repo.replace_holdings(
        session,
        account,
        PortfolioRequest(equity=[EquityHolding(symbol="TCS", quantity=1, avg_cost=100.0)]),
    )
    repo.replace_holdings(
        session,
        account,
        PortfolioRequest(equity=[EquityHolding(symbol="INFY", quantity=2, avg_cost=200.0)]),
    )
    session.commit()

    portfolio = repo.portfolio_for(session, account)
    assert [h.symbol for h in portfolio.equity] == ["INFY"]
    # The access key is the only way back to the account; only its hash is kept.
    assert repo.account_for_key(session, key).id == account.id
