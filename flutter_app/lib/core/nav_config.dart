import 'package:flutter/material.dart';

class NavItem {
  const NavItem(this.label, this.path, this.blurb, [this.icon = Icons.chevron_right]);
  final String label;
  final String path;
  final String blurb;
  final IconData icon;
}

class NavGroup {
  const NavGroup(this.label, this.items);
  final String label;
  final List<NavItem> items;
}

/// Single source of truth for the top navbar, mobile menu and footer.
const navGroups = <NavGroup>[
  NavGroup('Portfolio', [
    NavItem('Master Console', '/', 'NAV, tax status, hedges and alpha in one view', Icons.dashboard_outlined),
    NavItem('Holdings', '/portfolio/holdings', 'Positions, import from Fyers or a statement', Icons.account_balance_wallet_outlined),
    NavItem('Wealth Cone & VaR', '/portfolio', 'Projected range of outcomes and value at risk', Icons.show_chart),
    NavItem('Crash Simulator', '/portfolio/stress', 'Replay historical crises on your book', Icons.warning_amber_outlined),
    NavItem('Tax Rebalance', '/portfolio/rebalance', 'STCG / LTCG aware order sheet', Icons.balance_outlined),
    NavItem('Catalysts & News', '/portfolio/news', 'News and filings for what you hold', Icons.newspaper_outlined),
    NavItem('AI Memo', '/portfolio/memo', 'Monthly written review of your portfolio', Icons.description_outlined),
    NavItem('Watchlists', '/watchlists', 'Track companies you are researching', Icons.bookmark_border),
  ]),
  NavGroup('Research', [
    NavItem('Ask Iris', '/ask', 'Ask questions about listed companies', Icons.auto_awesome_outlined),
    NavItem('Screener', '/screener', 'Filter the NSE universe by fundamentals and technicals', Icons.filter_alt_outlined),
    NavItem('Equity Deep Dive', '/analyse', 'Piotroski, trend, sentiment and price history', Icons.search),
    NavItem('Ranked Alpha Board', '/recommendations', 'Explained buy / sell / hold calls', Icons.leaderboard_outlined),
    NavItem('Discovery', '/discovery', 'Theme baskets built from live screens', Icons.explore_outlined),
    NavItem('Mutual Funds', '/mutualfunds', 'NAV, returns and risk by scheme', Icons.pie_chart_outline),
    NavItem('Stocks A-Z', '/stocks', 'Browse every listed company', Icons.sort_by_alpha),
  ]),
  NavGroup('Markets', [
    NavItem('Market Today', '/market', 'Indices, breadth, gainers and losers', Icons.public),
    NavItem('Market Pulse', '/pulse', 'Breadth, volume shockers, breakouts', Icons.monitor_heart_outlined),
    NavItem('Macro Radar', '/macro', 'India macro and sector rotation', Icons.radar),
    NavItem('Market Movers', '/movers', 'Gainers, losers and most traded', Icons.swap_vert),
    NavItem('FII / DII Activity', '/fii-dii', 'Institutional flows', Icons.account_balance_outlined),
    NavItem('Bulk & Block Deals', '/bulk-block', 'Large negotiated trades', Icons.layers_outlined),
    NavItem('Corporate Actions', '/corporate-actions', 'Dividends, splits, bonuses', Icons.event_note_outlined),
    NavItem('Earnings Tracker', '/earnings', 'Quarterly results by financial year', Icons.insights_outlined),
    NavItem('Timeline', '/timeline', 'Company announcements and filings', Icons.timeline),
    NavItem('Concall Monitor', '/concalls', 'Management commentary tracker', Icons.record_voice_over_outlined),
    NavItem('IPO', '/ipo', 'Upcoming and listed issues', Icons.rocket_launch_outlined),
    NavItem('ETFs', '/etf', 'Exchange traded funds', Icons.stacked_bar_chart),
    NavItem('Indices', '/indices', 'Benchmark and sector indices', Icons.bar_chart),
    NavItem('Sectors', '/sectors', 'Sector and industry landscape', Icons.grid_view),
  ]),
  NavGroup('Derivatives & Quant', [
    NavItem('Options Chain & OI', '/options', 'PCR, max pain, OI walls', Icons.table_chart_outlined),
    NavItem('Tail Risk Sizer', '/options/tail-risk', 'Index put and collar sizing', Icons.shield_outlined),
    NavItem('Risk Parity (HRP)', '/quant', 'Weights, factors and regimes', Icons.hub_outlined),
  ]),
  NavGroup('Lab', [
    NavItem('Strategy Lab', '/lab', 'Event-driven walk-forward and Monte Carlo', Icons.science_outlined),
    NavItem('Paper Trading', '/paper', 'Persisted ledger with signal audit', Icons.receipt_long_outlined),
    NavItem('Backtest', '/backtest', 'Strategy vs buy-and-hold', Icons.history),
  ]),
  NavGroup('Tools', [
    NavItem('Alerts', '/alerts', 'Price and event alerts', Icons.notifications_none),
    NavItem('Calculators', '/calculators', 'SIP, lumpsum, SWP, PPF, FD, tax and more', Icons.calculate_outlined),
    NavItem('Pricing', '/pricing', 'Plans and limits', Icons.sell_outlined),
  ]),
];

/// Top-bar links: a plain link or a group dropdown.
const topLinks = <String>['Research', 'Markets', 'Portfolio', 'Derivatives & Quant', 'Lab'];
