import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/http_client.dart';
import '../../core/storage.dart';
import '../../core/theme.dart';
import '../../widgets/common.dart';

/// Generic page for a market-data feed. Renders the backend's own words when
/// the feed is not connected (never placeholder numbers).
class FeedPage extends StatelessWidget {
  const FeedPage({super.key, required this.kind, required this.title, required this.subtitle});
  final String kind, title, subtitle;
  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: title,
      subtitle: subtitle,
      children: [
        FutureBody<Json>(
          future: getJson('/api/market-data/$kind').then(asMap),
          builder: (r) {
            final items = asList(r['items']).map(asMap).toList();
            if (items.isEmpty) {
              return Panel(
                child: EmptyState(
                  icon: Icons.cable_outlined,
                  title: r['source'] == 'not_connected' ? 'Data source not connected' : 'Nothing to show',
                  message: (r['reason'] ?? 'No items returned.').toString(),
                ),
              );
            }
            final cols = items.first.keys.take(6).toList();
            return Panel(
              padding: EdgeInsets.zero,
              child: DataTableX(columns: cols, numericFrom: 99, rows: [for (final i in items) [for (final c in cols) i[c]?.toString() ?? '-']]),
            );
          },
        ),
      ],
    );
  }
}

// ----------------------------------------------------------- market today

class MarketTodayPage extends StatelessWidget {
  const MarketTodayPage({super.key});
  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Market Today',
      subtitle: 'Indices, volatility, breadth and sector leadership from live data.',
      children: [
        FutureBody<List<Json>>(
          future: Future.wait([getJson('/api/macro').then(asMap), getJson('/api/market-pulse').then(asMap)]),
          builder: (res) {
            final m = res[0], p = res[1];
            final idx = asMap(m['indices']);
            final b = asMap(p['breadth']);
            final sectors = asList(m['sector_rotation']).map(asMap).toList();
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              if (m['available'] == false) EmptyState(title: 'Index data unavailable', message: (m['reason'] ?? '').toString()) else ResponsiveGrid(children: [
                KpiCard(label: 'NIFTY 50', value: fmtNum(asNum(asMap(idx['nifty50'])['current'])), delta: asNum(asMap(idx['nifty50'])['change_pct'])),
                KpiCard(label: 'SENSEX', value: fmtNum(asNum(asMap(idx['sensex'])['current'])), delta: asNum(asMap(idx['sensex'])['change_pct'])),
                KpiCard(label: 'India VIX', value: fmtNum(asNum(asMap(m['vix'])['current']))),
                KpiCard(label: 'Advance / decline', value: '${b['advances'] ?? '-'} / ${b['declines'] ?? '-'}', caption: (b['sentiment'] ?? '').toString().replaceAll('_', ' ')),
              ]),
              const SizedBox(height: 16),
              Panel(
                title: 'Sector performance',
                padding: EdgeInsets.zero,
                child: DataTableX(columns: const ['Sector', '1M', '3M', 'Status'], rows: [
                  for (final s in sectors)
                    [s['name'], fmtPct(asNum(s['return_1m_pct'])), fmtPct(asNum(s['return_3m_pct'])), StatusPill(s['status'].toString(), tone: s['status'] == 'LEADERSHIP' ? Tone.buy : (s['status'] == 'LAGGING' ? Tone.sell : Tone.neutral))]
                ]),
              ),
              const SizedBox(height: 12),
              TextButton(onPressed: () => context.go('/pulse'), child: const Text('Volume shockers and breakouts in Market Pulse →')),
            ]);
          },
        ),
      ],
    );
  }
}

// -------------------------------------------------------------- discovery

/// Theme baskets built from live screener queries. Counts and members come
/// from the screener, not from a hard-coded list of companies.
const _themes = <(String, String, Map<String, Object?>)>[
  ('Quality compounders', 'High returns on capital with low debt.', {'min_roce': 18, 'max_debt_to_equity': 0.5, 'min_score': 55}),
  ('Growth at a reasonable price', 'Growing sales without a stretched P/E.', {'min_sales_growth': 15, 'max_pe': 30, 'min_score': 55}),
  ('Trend leaders', 'Above the 200-day average with a golden cross.', {'above_sma200': true, 'golden_cross': true, 'min_score': 60}),
  ('Low pledge, high ROE', 'Strong equity returns with little promoter pledging.', {'min_roe': 18, 'max_pledged_pct': 5, 'min_score': 50}),
];

class DiscoveryPage extends StatefulWidget {
  const DiscoveryPage({super.key});
  @override
  State<DiscoveryPage> createState() => _DiscoveryPageState();
}

class _DiscoveryPageState extends State<DiscoveryPage> {
  int? _open;
  Future<Json>? _run;

  void _go(int i) => setState(() {
        _open = i;
        _run = getJson('/api/screener/run${queryString({..._themes[i].$3, 'limit': 30, 'with_fundamentals': true})}').then(asMap);
      });

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Discovery',
      subtitle: 'Theme baskets are live screens. Open one to see which companies qualify right now.',
      children: [
        ResponsiveGrid(columns: 2, children: [
          for (var i = 0; i < _themes.length; i++)
            InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => _go(i),
              child: Panel(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Expanded(child: Text(_themes[i].$1, style: AppText.sans(size: 16, weight: FontWeight.w600))),
                    if (_open == i) const StatusPill('Open', tone: Tone.primary),
                  ]),
                  const SizedBox(height: 6),
                  Text(_themes[i].$2, style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.45)),
                  const SizedBox(height: 10),
                  Text(_themes[i].$3.entries.where((e) => e.key != 'min_score').map((e) => '${e.key.replaceAll('_', ' ')} ${e.value}').join(' · '), style: AppText.mono(size: 11, color: Palette.inkMuted)),
                ]),
              ),
            ),
        ]),
        const SizedBox(height: 20),
        if (_run != null)
          FutureBody<Json>(
            future: _run!,
            builder: (r) {
              final rows = asList(r['results']).map(asMap).toList();
              return Panel(
                title: '${_themes[_open!].$1}: ${rows.length} companies',
                padding: EdgeInsets.zero,
                child: DataTableX(
                  columns: const ['Company', 'Score', 'Price', 'P/E', 'ROCE %'],
                  onRowTap: (i) => context.go('/analyse/${Uri.encodeComponent(rows[i]['symbol'].toString())}'),
                  rows: [for (final x in rows) ['${x['name'] ?? x['symbol']}  ·  ${x['symbol']}', fmtNum(asNum(x['score']), dp: 0), fmtNum(asNum(x['price'])), fmtNum(asNum(x['pe_ratio']), dp: 1), fmtNum(asNum(x['roce_pct']), dp: 1)]],
                ),
              );
            },
          ),
      ],
    );
  }
}

// -------------------------------------------------------------- watchlist

const _watchKey = 'stockportfolio.watchlist.v1';

class WatchlistPage extends StatefulWidget {
  const WatchlistPage({super.key});
  @override
  State<WatchlistPage> createState() => _WatchlistPageState();
}

class _WatchlistPageState extends State<WatchlistPage> {
  final _symbol = TextEditingController();
  late final List<String> _list = prefs.getStringList(_watchKey) ?? [];

  void _save() => prefs.setStringList(_watchKey, _list);

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Watchlists',
      subtitle: 'Companies you are researching. Stored on this device.',
      children: [
        Panel(
          child: Row(children: [
            SizedBox(width: 240, child: TextField(controller: _symbol, decoration: const InputDecoration(labelText: 'Symbol (e.g. TCS)'), onSubmitted: (_) => _add())),
            const SizedBox(width: 12),
            FilledButton(onPressed: _add, child: const Text('Add')),
          ]),
        ),
        const SizedBox(height: 16),
        if (_list.isEmpty)
          const EmptyState(icon: Icons.bookmark_border, title: 'Your watchlist is empty', message: 'Add a symbol above to track it.')
        else
          Panel(
            padding: EdgeInsets.zero,
            child: Column(children: [
              for (final s in _list)
                FutureBuilder<Json>(
                  future: getJson('/api/stocks/analyse${queryString({'ticker': s, 'timeframe': 'week'})}').then(asMap),
                  builder: (context, snap) {
                    final d = snap.data ?? {};
                    return ListTile(
                      onTap: () => context.go('/analyse/${Uri.encodeComponent(s)}'),
                      title: Text(s, style: AppText.sans(weight: FontWeight.w600)),
                      subtitle: Text((d['name'] ?? (snap.hasError ? 'Could not load' : '')).toString(), style: AppText.sans(size: 12, color: Palette.inkSecondary)),
                      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                        if (d['price'] != null) Text(fmtNum(asNum(d['price'])), style: AppText.mono()),
                        const SizedBox(width: 10),
                        if (asNum(d['change_pct']) != null) DeltaBadge(asNum(d['change_pct'])!),
                        IconButton(icon: const Icon(Icons.close, size: 18), onPressed: () => setState(() { _list.remove(s); _save(); })),
                      ]),
                    );
                  },
                ),
            ]),
          ),
      ],
    );
  }

  void _add() {
    final s = _symbol.text.trim().toUpperCase();
    if (s.isEmpty || _list.contains(s)) return;
    setState(() {
      _list.add(s);
      _save();
      _symbol.clear();
    });
  }
}

// -------------------------------------------------------------- Ask Iris

class AskPage extends StatelessWidget {
  const AskPage({super.key});
  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Ask Iris',
      subtitle: 'Questions about listed companies, answered from filings with sources shown.',
      children: [
        FutureBody<Json>(
          future: getJson('/api/ai/status').then(asMap),
          builder: (s) => Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              EmptyState(
                icon: Icons.auto_awesome_outlined,
                title: 'Conversational research is not connected yet',
                message:
                    'The backend can write a verified monthly portfolio memo today (${s['configured'] == true ? 'AI model configured' : 'AI model not configured'}), but it has no filings index or chat endpoint, so free-form questions would have nothing real to answer from.',
                action: FilledButton(onPressed: () => context.go('/portfolio/memo'), child: const Text('Open the AI memo')),
              ),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        TextField(enabled: false, decoration: const InputDecoration(hintText: 'Ask about a company…  (available once a filings source is connected)')),
      ],
    );
  }
}

// ----------------------------------------------------------------- alerts

class AlertsPage extends StatefulWidget {
  const AlertsPage({super.key});
  @override
  State<AlertsPage> createState() => _AlertsPageState();
}

class _AlertsPageState extends State<AlertsPage> {
  static const _key = 'stockportfolio.alerts.v1';
  final _symbol = TextEditingController();
  final _price = TextEditingController();
  String _dir = 'above';
  late final List<String> _rules = prefs.getStringList(_key) ?? [];

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Alerts',
      subtitle: 'Define price rules here. Delivery by WhatsApp, email or push is not connected yet, so rules are saved but nothing is sent.',
      children: [
        Panel(
          title: 'New price alert',
          child: Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.end, children: [
            SizedBox(width: 160, child: TextField(controller: _symbol, decoration: const InputDecoration(labelText: 'Symbol'))),
            SegTabs(labels: const ['Above', 'Below'], index: _dir == 'above' ? 0 : 1, onChanged: (i) => setState(() => _dir = i == 0 ? 'above' : 'below')),
            SizedBox(width: 140, child: TextField(controller: _price, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Price (₹)'))),
            FilledButton(
              onPressed: () {
                final s = _symbol.text.trim().toUpperCase();
                if (s.isEmpty || double.tryParse(_price.text) == null) return;
                setState(() {
                  _rules.add('$s|$_dir|${_price.text.trim()}');
                  prefs.setStringList(_key, _rules);
                  _symbol.clear();
                  _price.clear();
                });
              },
              child: const Text('Save rule'),
            ),
          ]),
        ),
        const SizedBox(height: 16),
        Panel(
          title: 'Saved rules',
          padding: EdgeInsets.zero,
          child: _rules.isEmpty
              ? const EmptyState(icon: Icons.notifications_none, title: 'No alert rules yet')
              : Column(children: [
                  for (final r in _rules)
                    ListTile(
                      title: Text('${r.split('|')[0]} ${r.split('|')[1]} ₹${r.split('|')[2]}', style: AppText.mono(size: 14)),
                      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                        const StatusPill('Not delivered', tone: Tone.hold),
                        IconButton(icon: const Icon(Icons.close, size: 18), onPressed: () => setState(() { _rules.remove(r); prefs.setStringList(_key, _rules); })),
                      ]),
                    ),
                ]),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------- pricing

class PricingPage extends StatelessWidget {
  const PricingPage({super.key});
  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Pricing',
      subtitle: 'There is no paid plan yet. Everything in the app is free while it is in development.',
      children: [
        Panel(
          title: 'Early access',
          trailing: const StatusPill('Free', tone: Tone.buy),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            for (final f in const [
              'Portfolio valuation, risk and tax-aware rebalancing',
              'Ranked buy / sell / hold calls with evidence',
              'Screener, equity deep dive, mutual fund analytics',
              'Options chain, tail-risk sizing, HRP and factor analysis',
              'Strategy lab, paper trading and backtests',
              'Calculators and watchlists',
            ])
              Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Text('✓  $f', style: AppText.sans(size: 14, color: Palette.ink))),
            const SizedBox(height: 14),
            Text('Paid tiers, if introduced, will be announced here before any billing starts.', style: AppText.sans(size: 13, color: Palette.inkSecondary)),
          ]),
        ),
      ],
    );
  }
}
