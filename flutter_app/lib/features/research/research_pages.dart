import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/http_client.dart';
import '../../core/theme.dart';
import '../../widgets/charts.dart';
import '../../widgets/common.dart';
import '../portfolio/portfolio_store.dart';

Tone actionTone(String? a) => switch (a) {
      'STRONG_BUY' || 'BUY' => Tone.buy,
      'HOLD' => Tone.hold,
      'REDUCE' || 'EXIT' => Tone.sell,
      _ => Tone.neutral,
    };

Widget actionPill(Json r) => StatusPill((r['action_label'] ?? r['action'] ?? '-').toString().replaceAll('_', ' '), tone: actionTone(r['action']?.toString()));

// ------------------------------------------------------------- screener

class ScreenerPage extends StatefulWidget {
  const ScreenerPage({super.key});
  @override
  State<ScreenerPage> createState() => _ScreenerPageState();
}

class _ScreenerPageState extends State<ScreenerPage> {
  String? _index, _sector, _cap;
  double _minScore = 0;
  final _maxPe = TextEditingController();
  final _minRoce = TextEditingController();
  Future<Json>? _run;
  late final Future<Json> _filters = getJson('/api/screener/filters').then(asMap);

  void _go() => setState(() => _run = getJson('/api/screener/run${queryString({
            'index': _index,
            'sector': _sector,
            'cap': _cap,
            'min_score': _minScore > 0 ? _minScore.round() : null,
            'max_pe': double.tryParse(_maxPe.text),
            'min_roce': double.tryParse(_minRoce.text),
            'limit': 100,
            'with_fundamentals': true,
          })}').then(asMap));

  Widget _drop(String label, String? value, List<dynamic> options, ValueChanged<String?> onChanged) => SizedBox(
        width: 180,
        child: DropdownButtonFormField<String?>(
          initialValue: value,
          isExpanded: true,
          decoration: InputDecoration(labelText: label),
          items: [
            const DropdownMenuItem(value: null, child: Text('Any')),
            for (final o in options) DropdownMenuItem(value: o.toString(), child: Text(o.toString(), overflow: TextOverflow.ellipsis)),
          ],
          onChanged: onChanged,
        ),
      );

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Screener',
      subtitle: 'The NSE universe ranked by a technical and fundamental score. Fundamentals are scored for the top candidates only.',
      children: [
        Panel(
          child: FutureBuilder<Json>(
            future: _filters,
            builder: (context, snap) {
              final f = snap.data ?? {};
              return Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.end, children: [
                _drop('Index', _index, asList(f['indices']), (v) => setState(() => _index = v)),
                _drop('Sector', _sector, asList(f['sectors']), (v) => setState(() => _sector = v)),
                _drop('Market cap', _cap, asList(f['caps']), (v) => setState(() => _cap = v)),
                SizedBox(width: 120, child: TextField(controller: _maxPe, decoration: const InputDecoration(labelText: 'Max P/E'), keyboardType: TextInputType.number)),
                SizedBox(width: 120, child: TextField(controller: _minRoce, decoration: const InputDecoration(labelText: 'Min ROCE %'), keyboardType: TextInputType.number)),
                SizedBox(
                  width: 220,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('MIN SCORE  ${_minScore.round()}', style: AppText.label()),
                    Slider(value: _minScore, max: 100, divisions: 20, onChanged: (v) => setState(() => _minScore = v)),
                  ]),
                ),
                FilledButton(onPressed: _go, child: const Text('Run screen')),
              ]);
            },
          ),
        ),
        const SizedBox(height: 16),
        if (_run == null)
          const EmptyState(icon: Icons.filter_alt_outlined, title: 'Set filters and run', message: 'A first run can take a while as the universe is scored.')
        else
          FutureBody<Json>(
            future: _run!,
            builder: (r) {
              final rows = asList(r['results']).map(asMap).toList();
              return Panel(
                title: '${r['count'] ?? rows.length} results · scanned ${r['scanned'] ?? '-'} of ${r['universe'] ?? '-'}',
                padding: EdgeInsets.zero,
                child: DataTableX(
                  columns: const ['Company', 'Score', 'Call', 'Price', 'RSI', 'P/E', 'ROCE %', 'Sales gr. %'],
                  numericFrom: 1,
                  onRowTap: (i) => context.go('/analyse/${Uri.encodeComponent(rows[i]['symbol'].toString())}'),
                  rows: [
                    for (final x in rows)
                      [
                        '${x['name'] ?? x['symbol']}  ·  ${x['symbol']}',
                        fmtNum(asNum(x['score']), dp: 0),
                        actionPill(x),
                        fmtNum(asNum(x['price'])),
                        fmtNum(asNum(x['rsi14']), dp: 0),
                        fmtNum(asNum(x['pe_ratio']), dp: 1),
                        fmtNum(asNum(x['roce_pct']), dp: 1),
                        fmtNum(asNum(x['sales_growth_pct']), dp: 1),
                      ]
                  ],
                ),
              );
            },
          ),
      ],
    );
  }
}

// -------------------------------------------------------------- analyse

class AnalyseIndexPage extends StatefulWidget {
  const AnalyseIndexPage({super.key});
  @override
  State<AnalyseIndexPage> createState() => _AnalyseIndexPageState();
}

class _AnalyseIndexPageState extends State<AnalyseIndexPage> {
  final _q = TextEditingController();
  Future<dynamic>? _results;

  void _search() {
    if (_q.text.trim().length < 2) return;
    setState(() => _results = getJson('/api/stocks/search${queryString({'q': _q.text.trim()})}'));
  }

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Equity Deep Dive',
      subtitle: 'Search any listed company for its price history, technicals, sentiment and a score.',
      children: [
        Panel(
          child: Row(children: [
            Expanded(
              child: TextField(
                controller: _q,
                onSubmitted: (_) => _search(),
                decoration: const InputDecoration(hintText: 'Company name or ticker', prefixIcon: Icon(Icons.search)),
              ),
            ),
            const SizedBox(width: 12),
            FilledButton(onPressed: _search, child: const Text('Search')),
          ]),
        ),
        const SizedBox(height: 16),
        if (_results == null)
          const EmptyState(icon: Icons.search, title: 'Search for a company', message: 'Results come from the live symbol master.')
        else
          FutureBody<dynamic>(
            future: _results!,
            builder: (d) {
              final list = asList(d is Map ? (d['results'] ?? d['items'] ?? d['stocks']) : d).map(asMap).toList();
              if (list.isEmpty) return const EmptyState(title: 'No matches');
              return Panel(
                padding: EdgeInsets.zero,
                child: Column(children: [
                  for (final r in list)
                    ListTile(
                      title: Text((r['name'] ?? r['company'] ?? r['symbol']).toString(), style: AppText.sans(weight: FontWeight.w600)),
                      subtitle: Text((r['symbol'] ?? r['ticker'] ?? '').toString(), style: AppText.mono(size: 12)),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.go('/analyse/${Uri.encodeComponent((r['symbol'] ?? r['ticker']).toString())}'),
                    ),
                ]),
              );
            },
          ),
      ],
    );
  }
}

class AnalyseTickerPage extends StatefulWidget {
  const AnalyseTickerPage({super.key, required this.ticker});
  final String ticker;
  @override
  State<AnalyseTickerPage> createState() => _AnalyseTickerPageState();
}

class _AnalyseTickerPageState extends State<AnalyseTickerPage> {
  static const _frames = ['week', 'month', 'quarter', 'year'];
  int _tf = 1;
  late Future<Json> _data = _load();

  Future<Json> _load() =>
      getJson('/api/stocks/analyse${queryString({'ticker': widget.ticker, 'timeframe': _frames[_tf]})}').then(asMap);

  @override
  void didUpdateWidget(covariant AnalyseTickerPage old) {
    super.didUpdateWidget(old);
    if (old.ticker != widget.ticker) _data = _load();
  }

  @override
  Widget build(BuildContext context) {
    return PageBox(
      child: FutureBody<Json>(
        future: _data,
        builder: (d) {
          final tech = asMap(d['technicals']);
          final sent = asMap(d['sentiment']);
          final rec = asMap(d['recommendation']);
          final det = asMap(d['details']);
          final chart = asList(d['chart_data']).map(asMap).toList();
          final pts = [for (var i = 0; i < chart.length; i++) FlSpot(i.toDouble(), asNum(chart[i]['close']) ?? 0)];
          final change = asNum(d['change_pct']);
          final decision = (rec['decision'] ?? '').toString();
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            PageHeader(
              title: (d['name'] ?? widget.ticker).toString(),
              subtitle: widget.ticker,
              actions: [
                OutlinedButton(onPressed: () => context.go('/analyse'), child: const Text('Search another')),
              ],
            ),
            ResponsiveGrid(children: [
              KpiCard(label: 'Price', value: fmtNum(asNum(d['price'])), delta: change),
              KpiCard(label: 'Score', value: '${rec['score'] ?? '-'}', caption: decision),
              KpiCard(label: 'RSI (14)', value: fmtNum(asNum(tech['rsi']), dp: 1), caption: (tech['rsi_desc'] ?? '').toString()),
              KpiCard(label: 'Trend', value: (tech['trend'] ?? '-').toString()),
            ]),
            const SizedBox(height: 16),
            Panel(
              title: 'Price',
              trailing: SegTabs(
                labels: const ['1W', '1M', '3M', '1Y'],
                index: _tf,
                onChanged: (i) => setState(() {
                  _tf = i;
                  _data = _load();
                }),
              ),
              child: LineChartX(
                height: 300,
                yFormat: (v) => fmtNum(v, dp: 0),
                xFormat: (x) {
                  final i = x.round();
                  return i >= 0 && i < chart.length ? chart[i]['date'].toString().substring(5, 10) : '';
                },
                series: [Series('Close', pts, Palette.primary, area: true)],
              ),
            ),
            const SizedBox(height: 16),
            ResponsiveGrid(columns: 3, children: [
              Panel(title: 'Verdict', child: Text((rec['interpretation'] ?? 'No interpretation returned.').toString(), style: AppText.sans(size: 14, color: Palette.ink, height: 1.5))),
              Panel(
                title: 'Technicals',
                child: Column(children: [
                  for (final k in const ['sma20', 'sma50', 'sma200', 'ema20', 'ema50']) _row(k.toUpperCase(), fmtNum(asNum(tech[k]))),
                ]),
              ),
              Panel(
                title: 'Day range & 52 week',
                child: Column(children: [
                  _row('Day high', fmtNum(asNum(det['day_high']))),
                  _row('Day low', fmtNum(asNum(det['day_low']))),
                  _row('52w high', fmtNum(asNum(det['fifty_two_week_high']))),
                  _row('52w low', fmtNum(asNum(det['fifty_two_week_low']))),
                  _row('Volume', fmtNum(asNum(det['volume']), dp: 0)),
                ]),
              ),
            ]),
            const SizedBox(height: 16),
            Panel(
              title: 'News sentiment',
              trailing: StatusPill((sent['desc'] ?? 'n/a').toString(), tone: (asNum(sent['compound']) ?? 0) > 0.05 ? Tone.buy : ((asNum(sent['compound']) ?? 0) < -0.05 ? Tone.sell : Tone.neutral)),
              child: asList(d['news']).isEmpty
                  ? Text('No recent headlines.', style: AppText.sans(color: Palette.inkSecondary))
                  : Column(children: [
                      for (final n in asList(d['news']).map(asMap).take(8))
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(n['title'].toString(), style: AppText.sans(size: 14, weight: FontWeight.w500)),
                          subtitle: Text('${n['source'] ?? ''} · ${n['time'] ?? ''}', style: AppText.sans(size: 12, color: Palette.inkSecondary)),
                        ),
                    ]),
            ),
          ]);
        },
      ),
    );
  }

  Widget _row(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: Row(children: [Expanded(child: Text(k, style: AppText.sans(size: 13, color: Palette.inkSecondary))), Text(v, style: AppText.mono())]),
      );
}

// -------------------------------------------------------- recommendations

class RecommendationsPage extends StatefulWidget {
  const RecommendationsPage({super.key});
  @override
  State<RecommendationsPage> createState() => _RecommendationsPageState();
}

class _RecommendationsPageState extends State<RecommendationsPage> {
  int _tab = 0;
  late Future<Json> _data = _load();

  Future<Json> _load() {
    portfolioStore.ensureLoaded();
    final p = portfolioStore.portfolio;
    if (p.isEmpty) return getJson('/api/recommendations${queryString({'buy_limit': 15, 'sell_limit': 15})}').then(asMap);
    return postJson('/api/recommendations', {'buy_limit': 15, 'sell_limit': 15, 'portfolio': p.toJson()}).then(asMap);
  }

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Ranked Alpha Board',
      subtitle: 'Explained buy, sell and hold calls. Each row lists the evidence behind it; sells include the tax cost of exiting.',
      actions: [OutlinedButton(onPressed: () => setState(() => _data = _load()), child: const Text('Refresh'))],
      children: [
        FutureBody<Json>(
          future: _data,
          builder: (r) {
            final sum = asMap(r['summary']);
            final lists = [asList(r['buy']), asList(r['sell']), asList(r['holdings_to_keep'])].map((l) => l.map(asMap).toList()).toList();
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ResponsiveGrid(children: [
                KpiCard(label: 'Buy candidates', value: '${sum['buy'] ?? 0}'),
                KpiCard(label: 'Sell / reduce', value: '${sum['sell'] ?? 0}'),
                KpiCard(label: 'Holdings scored', value: '${sum['holdings_scored'] ?? 0}'),
                KpiCard(label: 'Basis', value: (r['basis'] ?? '-').toString(), caption: 'As of ${r['as_of'] ?? '-'}'),
              ]),
              const SizedBox(height: 20),
              SegTabs(
                labels: ['Buy (${lists[0].length})', 'Sell (${lists[1].length})', 'Hold (${lists[2].length})'],
                index: _tab,
                onChanged: (i) => setState(() => _tab = i),
              ),
              const SizedBox(height: 16),
              if (lists[_tab].isEmpty)
                const EmptyState(title: 'Nothing in this list', message: 'The ranker returned no names for this band.')
              else
                for (final row in lists[_tab]) _RecCard(row: row),
              const SizedBox(height: 8),
              Text((r['disclaimer'] ?? '').toString(), style: AppText.sans(size: 12, color: Palette.inkSecondary, height: 1.5)),
            ]);
          },
        ),
      ],
    );
  }
}

class _RecCard extends StatelessWidget {
  const _RecCard({required this.row});
  final Json row;
  @override
  Widget build(BuildContext context) {
    final pos = asMap(row['position']);
    final reasons = asList(row['reasons']);
    final warnings = asList(row['warnings']);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Panel(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: InkWell(
                onTap: () => context.go('/analyse/${Uri.encodeComponent(row['symbol'].toString())}'),
                child: Text('${row['name'] ?? row['symbol']}  ·  ${row['symbol']}', style: AppText.sans(size: 16, weight: FontWeight.w600)),
              ),
            ),
            actionPill(row),
            const SizedBox(width: 8),
            Text(fmtNum(asNum(row['score']), dp: 0), style: AppText.mono(size: 18, weight: FontWeight.w700)),
          ]),
          const SizedBox(height: 6),
          Text('${row['sector'] ?? ''} ${row['cap'] != null ? '· ${row['cap']}' : ''} · price ${fmtNum(asNum(row['price']))} · conviction ${row['conviction'] ?? '-'}',
              style: AppText.sans(size: 12, color: Palette.inkSecondary)),
          if (reasons.isNotEmpty) ...[
            const SizedBox(height: 10),
            for (final x in reasons) Text('• $x', style: AppText.sans(size: 13, color: Palette.ink, height: 1.5)),
          ],
          if (warnings.isNotEmpty) ...[
            const SizedBox(height: 8),
            for (final x in warnings) Text('⚠ $x', style: AppText.sans(size: 12, color: Palette.hold, height: 1.5)),
          ],
          if (pos.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(),
            const SizedBox(height: 10),
            Wrap(spacing: 28, runSpacing: 8, children: [
              _kv('Qty', fmtNum(asNum(pos['quantity']), dp: 2)),
              _kv('Avg cost', fmtNum(asNum(pos['avg_cost']))),
              _kv('P&L', fmtPct(asNum(pos['unrealised_pnl_pct']))),
              _kv('Held', '${pos['days_held'] ?? '-'} days (${pos['term'] ?? '-'})'),
              _kv('Exit tax', fmtInr(asNum(pos['estimated_exit_tax_inr']))),
              _kv('Net proceeds', fmtInr(asNum(pos['net_proceeds_inr']))),
            ]),
            if ((pos['note'] ?? '').toString().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(pos['note'].toString(), style: AppText.sans(size: 12, color: Palette.inkSecondary)),
            ],
          ],
        ]),
      ),
    );
  }

  Widget _kv(String k, String v) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(k.toUpperCase(), style: AppText.label()),
        const SizedBox(height: 3),
        Text(v, style: AppText.mono(size: 13, weight: FontWeight.w600)),
      ]);
}

// ----------------------------------------------------------------- pulse

class PulsePage extends StatefulWidget {
  const PulsePage({super.key});
  @override
  State<PulsePage> createState() => _PulsePageState();
}

class _PulsePageState extends State<PulsePage> {
  String _universe = 'NIFTY50';
  late Future<Json> _data = _load();
  Future<Json> _load() => getJson('/api/market-pulse${queryString({'universe': _universe})}').then(asMap);

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Market Pulse',
      subtitle: 'Breadth, volume shockers and breakout candidates across an index universe.',
      actions: [
        SegTabs(
          labels: const ['NIFTY 50', 'NIFTY 500'],
          index: _universe == 'NIFTY50' ? 0 : 1,
          onChanged: (i) => setState(() {
            _universe = i == 0 ? 'NIFTY50' : 'NIFTY500';
            _data = _load();
          }),
        )
      ],
      children: [
        FutureBody<Json>(
          future: _data,
          builder: (r) {
            if (r['available'] == false) return EmptyState(title: 'Pulse unavailable', message: (r['reason'] ?? '').toString());
            final b = asMap(r['breadth']);
            final shock = asList(r['volume_shockers']).map(asMap).toList();
            final brk = asList(r['breakouts']).map(asMap).toList();
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ResponsiveGrid(children: [
                KpiCard(label: 'Advancing', value: '${b['advances'] ?? '-'}', caption: '${fmtNum(asNum(b['advance_pct']), dp: 0)}% of ${b['total'] ?? '-'}'),
                KpiCard(label: 'Declining', value: '${b['declines'] ?? '-'}'),
                KpiCard(label: 'Breadth ratio', value: fmtNum(asNum(b['breadth_ratio']))),
                KpiCard(label: 'Sentiment', value: (b['sentiment'] ?? '-').toString().replaceAll('_', ' '), caption: (b['description'] ?? '').toString()),
              ]),
              const SizedBox(height: 16),
              Panel(
                title: 'Volume shockers',
                padding: EdgeInsets.zero,
                child: DataTableX(
                  columns: const ['Company', 'Price', 'Change', 'Volume surge', 'Tag'],
                  onRowTap: (i) => context.go('/analyse/${Uri.encodeComponent(shock[i]['symbol'].toString())}'),
                  rows: [
                    for (final s in shock)
                      [
                        '${s['name']}  ·  ${s['symbol']}',
                        fmtNum(asNum(s['current_price'])),
                        Text(fmtPct(asNum(s['change_pct'])), style: AppText.mono(color: deltaColor(asNum(s['change_pct'])))),
                        '${fmtNum(asNum(s['volume_surge_ratio']))}x',
                        StatusPill(s['tag'].toString().replaceAll('_', ' '), tone: s['tag'] == 'INSTITUTIONAL_ACCUMULATION' ? Tone.buy : Tone.primary),
                      ]
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Panel(
                title: 'Breakout candidates',
                padding: EdgeInsets.zero,
                child: DataTableX(
                  columns: const ['Company', 'Price', '52w high', 'Distance', 'Status'],
                  onRowTap: (i) => context.go('/analyse/${Uri.encodeComponent(brk[i]['symbol'].toString())}'),
                  rows: [
                    for (final s in brk)
                      [
                        '${s['name']}  ·  ${s['symbol']}',
                        fmtNum(asNum(s['current_price'])),
                        fmtNum(asNum(s['high_52w'])),
                        fmtPct(asNum(s['distance_pct']), sign: false),
                        StatusPill(s['status'].toString().replaceAll('_', ' '), tone: s['status'].toString().startsWith('NEW') ? Tone.buy : Tone.hold),
                      ]
                  ],
                ),
              ),
            ]);
          },
        ),
      ],
    );
  }
}

// ----------------------------------------------------------------- macro

class MacroPage extends StatelessWidget {
  const MacroPage({super.key});
  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Macro Radar',
      subtitle: 'India macro regime, commodity and currency pressure, and sector rotation.',
      children: [
        FutureBody<Json>(
          future: getJson('/api/macro').then(asMap),
          builder: (m) {
            if (m['available'] == false) return EmptyState(title: 'Macro data unavailable', message: (m['reason'] ?? '').toString());
            final reg = asMap(m['regime']);
            final crude = asMap(m['crude']);
            final fx = asMap(m['currency']);
            final idx = asMap(m['indices']);
            final sectors = asList(m['sector_rotation']).map(asMap).toList();
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ResponsiveGrid(children: [
                KpiCard(label: 'NIFTY 50', value: fmtNum(asNum(asMap(idx['nifty50'])['current'])), delta: asNum(asMap(idx['nifty50'])['change_pct'])),
                KpiCard(label: 'SENSEX', value: fmtNum(asNum(asMap(idx['sensex'])['current'])), delta: asNum(asMap(idx['sensex'])['change_pct'])),
                KpiCard(label: 'India VIX', value: fmtNum(asNum(asMap(m['vix'])['current'])), caption: '5d ${fmtPct(asNum(asMap(m['vix'])['change_5d_pct']))}'),
                KpiCard(label: 'US 10Y', value: fmtPct(asNum(asMap(m['us10y'])['yield_pct']), sign: false)),
              ]),
              const SizedBox(height: 16),
              Panel(
                title: (reg['title'] ?? 'Regime').toString(),
                trailing: StatusPill((reg['posture'] ?? '').toString(), tone: Tone.primary),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text((reg['narrative'] ?? '').toString(), style: AppText.sans(size: 14, color: Palette.ink, height: 1.55)),
                  const SizedBox(height: 12),
                  Text('Favoured: ${asList(reg['favored_sectors']).join(', ')}', style: AppText.sans(size: 13, color: Palette.buy)),
                  const SizedBox(height: 4),
                  Text('Unfavoured: ${asList(reg['unfavored_sectors']).join(', ')}', style: AppText.sans(size: 13, color: Palette.sell)),
                ]),
              ),
              const SizedBox(height: 16),
              ResponsiveGrid(columns: 2, children: [
                Panel(title: 'Crude oil', trailing: StatusPill((crude['pressure_level'] ?? '').toString(), tone: crude['pressure_level'] == 'ELEVATED' ? Tone.sell : (crude['pressure_level'] == 'MODERATE' ? Tone.hold : Tone.buy)), child: _macroBody(crude, 'current_price')),
                Panel(title: 'USD / INR', trailing: StatusPill((fx['stance'] ?? '').toString().replaceAll('_', ' '), tone: Tone.neutral), child: _macroBody(fx, 'current_rate')),
              ]),
              const SizedBox(height: 16),
              Panel(
                title: 'Sector rotation',
                padding: EdgeInsets.zero,
                child: DataTableX(
                  columns: const ['Sector', '1M', '3M', 'Rel. 1M', 'Momentum', 'Status'],
                  rows: [
                    for (final s in sectors)
                      [
                        s['name'],
                        fmtPct(asNum(s['return_1m_pct'])),
                        fmtPct(asNum(s['return_3m_pct'])),
                        fmtPct(asNum(s['relative_1m_pct'])),
                        fmtNum(asNum(s['momentum_score']), dp: 1),
                        StatusPill(s['status'].toString(), tone: switch (s['status']) { 'LEADERSHIP' => Tone.buy, 'IMPROVING' => Tone.primary, 'WEAKENING' => Tone.hold, _ => Tone.sell }),
                      ]
                  ],
                ),
              ),
            ]);
          },
        ),
      ],
    );
  }

  Widget _macroBody(Json m, String valueKey) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(fmtNum(asNum(m[valueKey])), style: AppText.mono(size: 22, weight: FontWeight.w600)),
        const SizedBox(height: 6),
        Text('5d ${fmtPct(asNum(m['change_5d_pct']))}  ·  20d ${fmtPct(asNum(m['change_20d_pct']))}', style: AppText.mono(size: 12, color: Palette.inkSecondary)),
        const SizedBox(height: 8),
        Text((m['impact_assessment'] ?? '').toString(), style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.45)),
      ]);
}

// ----------------------------------------------------------- mutual funds

class MutualFundsPage extends StatefulWidget {
  const MutualFundsPage({super.key});
  @override
  State<MutualFundsPage> createState() => _MutualFundsPageState();
}

class _MutualFundsPageState extends State<MutualFundsPage> {
  final _q = TextEditingController();
  bool _direct = true, _growth = true;
  Future<Json>? _res;

  void _search() {
    if (_q.text.trim().length < 2) return;
    setState(() => _res = getJson('/api/mf/search${queryString({'q': _q.text.trim(), 'limit': 50, 'direct_only': _direct, 'growth_only': _growth})}').then(asMap));
  }

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Mutual Funds',
      subtitle: 'Search a scheme for NAV history, trailing and rolling returns, and risk.',
      children: [
        Panel(
          child: Wrap(spacing: 12, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            SizedBox(width: 380, child: TextField(controller: _q, onSubmitted: (_) => _search(), decoration: const InputDecoration(hintText: 'Scheme name', prefixIcon: Icon(Icons.search)))),
            FilterChip(label: const Text('Direct only'), selected: _direct, onSelected: (v) => setState(() => _direct = v)),
            FilterChip(label: const Text('Growth only'), selected: _growth, onSelected: (v) => setState(() => _growth = v)),
            FilledButton(onPressed: _search, child: const Text('Search')),
          ]),
        ),
        const SizedBox(height: 16),
        if (_res == null)
          const EmptyState(icon: Icons.pie_chart_outline, title: 'Search for a fund')
        else
          FutureBody<Json>(
            future: _res!,
            builder: (r) {
              final list = asList(r['results']).map(asMap).toList();
              if (list.isEmpty) return const EmptyState(title: 'No schemes matched');
              return Panel(
                padding: EdgeInsets.zero,
                child: Column(children: [
                  for (final f in list)
                    ListTile(
                      title: Text(f['schemeName'].toString(), style: AppText.sans(weight: FontWeight.w500)),
                      subtitle: Text('Scheme ${f['schemeCode']}', style: AppText.mono(size: 12, color: Palette.inkSecondary)),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.go('/mutualfunds/${f['schemeCode']}'),
                    ),
                ]),
              );
            },
          ),
      ],
    );
  }
}

class FundDetailPage extends StatelessWidget {
  const FundDetailPage({super.key, required this.code});
  final String code;
  static const _labels = {'1m': '1 Month', '3m': '3 Months', '6m': '6 Months', '1y': '1 Year', '3y': '3 Years', '5y': '5 Years', '10y': '10 Years', 'since_inception': 'Since inception'};

  @override
  Widget build(BuildContext context) {
    return PageBox(
      child: FutureBody<List<Json>>(
        future: Future.wait([getJson('/api/mf/$code/analysis').then(asMap), getJson('/api/mf/$code').then(asMap)]),
        builder: (res) {
          final a = res[0], h = res[1];
          if (a['error'] != null) return ErrorState(a['error']!);
          final meta = asMap(a['meta']);
          final nav = asMap(a['nav']);
          final risk = asMap(a['risk']);
          final trailing = asMap(a['trailing_returns']);
          final rolling = asMap(a['rolling_returns']);
          // NAV dates arrive as DD-MM-YYYY, oldest last.
          final hist = asList(h['data']).map(asMap).toList().reversed.toList();
          final pts = [for (var i = 0; i < hist.length; i++) FlSpot(i.toDouble(), double.tryParse(hist[i]['nav'].toString()) ?? 0)];
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            PageHeader(title: (meta['scheme_name'] ?? 'Fund $code').toString(), subtitle: '${meta['fund_house'] ?? ''} · ${meta['scheme_category'] ?? ''}'),
            ResponsiveGrid(children: [
              KpiCard(label: 'Latest NAV', value: fmtNum(asNum(nav['latest'])), caption: (nav['latest_date'] ?? '').toString()),
              KpiCard(label: 'Volatility', value: fmtPct(asNum(risk['volatility_pct']), sign: false)),
              KpiCard(label: 'Sharpe', value: fmtNum(asNum(risk['sharpe_ratio']))),
              KpiCard(label: 'Max drawdown', value: fmtPct(asNum(risk['max_drawdown_pct']), sign: false)),
            ]),
            const SizedBox(height: 16),
            Panel(title: 'NAV history', child: LineChartX(height: 280, yFormat: (v) => fmtNum(v), xFormat: (x) { final i = x.round(); return i >= 0 && i < hist.length ? hist[i]['date'].toString().substring(6) : ''; }, series: [Series('NAV', pts, Palette.primary, area: true)])),
            const SizedBox(height: 16),
            Panel(
              title: 'Trailing returns',
              padding: EdgeInsets.zero,
              child: DataTableX(
                columns: const ['Period', 'Return', 'CAGR'],
                rows: [
                  for (final e in _labels.entries)
                    if (trailing[e.key] != null)
                      [e.value, fmtPct(asNum(asMap(trailing[e.key])['return_pct'])), fmtPct(asNum(asMap(trailing[e.key])['cagr_pct']))]
                ],
              ),
            ),
            const SizedBox(height: 16),
            Panel(
              title: 'Rolling returns',
              padding: EdgeInsets.zero,
              child: DataTableX(
                columns: const ['Window', 'Average', 'Median', 'Min', 'Max', 'Positive windows'],
                rows: [
                  for (final e in rolling.entries)
                    if (asMap(e.value)['insufficient_data'] != true)
                      [
                        '${asMap(e.value)['years'] ?? e.key} year',
                        fmtPct(asNum(asMap(e.value)['average_pct'])),
                        fmtPct(asNum(asMap(e.value)['median_pct'])),
                        fmtPct(asNum(asMap(e.value)['min_pct'])),
                        fmtPct(asNum(asMap(e.value)['max_pct'])),
                        fmtPct(asNum(asMap(e.value)['positive_windows_pct']), sign: false),
                      ]
                ],
              ),
            ),
          ]);
        },
      ),
    );
  }
}
