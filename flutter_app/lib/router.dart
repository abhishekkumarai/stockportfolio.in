import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'core/auth/auth_controller.dart';
import 'core/nav_config.dart';
import 'features/auth/auth_screen.dart';
import 'features/derivatives/derivatives_pages.dart';
import 'features/landing/landing_screen.dart';
import 'features/markets/market_pages.dart';
import 'features/tools/calculators_page.dart';
import 'features/portfolio/console_page.dart';
import 'features/portfolio/portfolio_pages.dart';
import 'features/research/company_page.dart';
import 'features/research/research_pages.dart';
import 'widgets/app_shell.dart';
import 'widgets/common.dart';

/// Routes reachable without signing in (mirrors middleware.ts allow-list,
/// plus the public landing and static pages).
const _public = {'/auth', '/welcome', '/pricing', '/calculators'};

/// Page builders registered by feature modules; anything not registered yet
/// falls back to [PendingPage] so the shell and nav are always complete.
final Map<String, Widget Function(GoRouterState)> pageBuilders = {
  '/welcome': (_) => const LandingScreen(),
  '/': (_) => const ConsolePage(),
  '/portfolio': (_) => const PortfolioOverviewPage(),
  '/portfolio/holdings': (_) => const HoldingsPage(),
  '/portfolio/stress': (_) => const StressPage(),
  '/portfolio/rebalance': (_) => const RebalancePage(),
  '/portfolio/news': (_) => const NewsPage(),
  '/portfolio/memo': (_) => const MemoPage(),
  '/screener': (_) => const ScreenerPage(),
  '/analyse': (_) => const AnalyseIndexPage(),
  '/recommendations': (_) => const RecommendationsPage(),
  '/pulse': (_) => const PulsePage(),
  '/macro': (_) => const MacroPage(),
  '/mutualfunds': (_) => const MutualFundsPage(),
  '/options': (_) => const OptionsPage(),
  '/options/tail-risk': (_) => const TailRiskPage(),
  '/quant': (_) => const QuantPage(),
  '/lab': (_) => const LabPage(),
  '/paper': (_) => const PaperPage(),
  '/backtest': (_) => const BacktestPage(),
  '/calculators': (_) => const CalculatorsHubPage(),
  '/market': (_) => const MarketTodayPage(),
  '/discovery': (_) => const DiscoveryPage(),
  '/watchlists': (_) => const WatchlistPage(),
  '/ask': (_) => const AskPage(),
  '/alerts': (_) => const AlertsPage(),
  '/pricing': (_) => const PricingPage(),
  '/stocks': (_) => const AnalyseIndexPage(),
  '/movers': (_) => const FeedPage(kind: 'movers', title: 'Market Movers', subtitle: 'Gainers, losers and most traded by volume and value.'),
  '/fii-dii': (_) => const FeedPage(kind: 'fii-dii', title: 'FII / DII Activity', subtitle: 'Daily institutional flows.'),
  '/bulk-block': (_) => const FeedPage(kind: 'bulk-block', title: 'Bulk & Block Deals', subtitle: 'Large negotiated trades.'),
  '/corporate-actions': (_) => const FeedPage(kind: 'corporate-actions', title: 'Corporate Actions', subtitle: 'Dividends, splits and bonuses.'),
  '/earnings': (_) => const FeedPage(kind: 'earnings', title: 'Earnings Tracker', subtitle: 'Quarterly results and beat rates by financial year.'),
  '/timeline': (_) => const FeedPage(kind: 'timeline', title: 'Timeline', subtitle: 'Company announcements and exchange filings.'),
  '/concalls': (_) => const FeedPage(kind: 'concalls', title: 'Concall Monitor', subtitle: 'Management commentary from earnings calls.'),
  '/ipo': (_) => const FeedPage(kind: 'ipo', title: 'IPO', subtitle: 'Upcoming, open and listed issues.'),
  '/etf': (_) => const FeedPage(kind: 'etf', title: 'ETFs', subtitle: 'Exchange traded funds.'),
  '/indices': (_) => const FeedPage(kind: 'indices', title: 'Indices', subtitle: 'Benchmark and sector indices.'),
  '/sectors': (_) => const FeedPage(kind: 'sectors', title: 'Sectors', subtitle: 'Sector and industry landscape.'),
};

final appRouter = GoRouter(
  initialLocation: '/',
  refreshListenable: auth,
  redirect: (context, state) {
    final path = state.uri.path;
    final isPublic = _public.contains(path) || path.startsWith('/calculators/');
    if (!auth.isAuthenticated && !isPublic) {
      // Signed-out visitors see the landing page at the root, the login
      // screen (with a return path) everywhere else.
      if (path == '/') return '/welcome';
      return '/auth?redirect=${Uri.encodeComponent(state.uri.toString())}';
    }
    if (auth.isAuthenticated && path == '/auth') return '/';
    return null;
  },
  routes: [
    GoRoute(
      path: '/auth',
      builder: (_, s) => AuthScreen(redirect: s.uri.queryParameters['redirect']),
    ),
    ShellRoute(
      builder: (_, _, child) => AppShell(child: child),
      routes: [
        GoRoute(path: '/', pageBuilder: (c, s) => _page(s, _build(s))),
        for (final g in navGroups)
          for (final i in g.items)
            if (i.path != '/') GoRoute(path: i.path, pageBuilder: (c, s) => _page(s, _build(s))),
        GoRoute(path: '/welcome', pageBuilder: (c, s) => _page(s, _build(s))),
        GoRoute(path: '/analyse/:ticker', pageBuilder: (c, s) => _page(s, _build(s))),
        GoRoute(path: '/mutualfunds/:schemeCode', pageBuilder: (c, s) => _page(s, _build(s))),
        GoRoute(path: '/calculators/:kind', pageBuilder: (c, s) => _page(s, _build(s))),
      ],
    ),
  ],
);

Widget _build(GoRouterState s) {
  final ticker = s.pathParameters['ticker'];
  if (ticker != null) return CompanyPage(key: ValueKey(ticker), ticker: ticker);
  final kind = s.pathParameters['kind'];
  if (kind != null) return CalculatorPage(key: ValueKey(kind), slug: kind);
  final code = s.pathParameters['schemeCode'];
  if (code != null) return FundDetailPage(key: ValueKey(code), code: code);
  final b =pageBuilders[s.uri.path] ?? pageBuilders[s.matchedLocation];
  return b != null ? b(s) : PendingPage(path: s.uri.path);
}

Page<void> _page(GoRouterState s, Widget child) =>
    NoTransitionPage<void>(key: s.pageKey, child: child);

class PendingPage extends StatelessWidget {
  const PendingPage({super.key, required this.path});
  final String path;
  @override
  Widget build(BuildContext context) {
    String title = path;
    for (final g in navGroups) {
      for (final i in g.items) {
        if (i.path == path) title = i.label;
      }
    }
    return PageScaffold(
      title: title,
      children: const [EmptyState(title: 'Not built yet', message: 'This page is scheduled in a later phase.')],
    );
  }
}
