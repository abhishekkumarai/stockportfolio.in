import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/http_client.dart';
import '../../core/theme.dart';
import '../../widgets/charts.dart';
import '../../widgets/common.dart';

/// Tabbed company page (REC-130). Every tab reads real backend data; a tab
/// whose source is not connected says so rather than showing placeholders.
const _tabs = ['Overview', 'Technicals', 'Financials', 'Shareholdings', 'Peers', 'Projection', 'Documents', 'Actions', 'Announcements'];

class CompanyPage extends StatefulWidget {
  const CompanyPage({super.key, required this.ticker});
  final String ticker;
  @override
  State<CompanyPage> createState() => _CompanyPageState();
}

class _CompanyPageState extends State<CompanyPage> {
  int _tab = 0;
  late final Future<Json> _analysis = getJson('/api/stocks/analyse${queryString({'ticker': widget.ticker, 'timeframe': 'month'})}').then(asMap);

  @override
  Widget build(BuildContext context) {
    return PageBox(
      child: FutureBody<Json>(
        future: _analysis,
        builder: (a) {
          final change = asNum(a['change_pct']);
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            PageHeader(
              title: (a['name'] ?? widget.ticker).toString(),
              subtitle: widget.ticker,
              actions: [OutlinedButton(onPressed: () => context.go('/analyse'), child: const Text('Search another'))],
            ),
            Wrap(spacing: 14, crossAxisAlignment: WrapCrossAlignment.center, children: [
              Text(fmtInr(asNum(a['price']), dp: 2), style: AppText.mono(size: 28, weight: FontWeight.w700)),
              if (change != null) DeltaBadge(change),
            ]),
            const SizedBox(height: 18),
            SegTabs(labels: _tabs, index: _tab, onChanged: (i) => setState(() => _tab = i)),
            const SizedBox(height: 18),
            switch (_tab) {
              0 => OverviewTab(ticker: widget.ticker, analysis: a),
              1 => TechnicalsTab(ticker: widget.ticker, analysis: a),
              2 => FinancialsTab(ticker: widget.ticker),
              3 => ShareholdingTab(ticker: widget.ticker),
              4 => const _Pending(title: 'Peers', message: 'Peer comparison is tracked in REC-134.'),
              5 => const _Pending(title: 'Projection', message: 'A model-based projection (not an analyst forecast) is tracked in REC-136.'),
              _ => _NotConnected(title: _tabs[_tab], message: 'Company filings, corporate actions and announcements need the Epic 16 data feeds (REC-110).'),
            },
          ]);
        },
      ),
    );
  }
}

class _Pending extends StatelessWidget {
  const _Pending({required this.title, required this.message});
  final String title, message;
  @override
  Widget build(BuildContext context) => Panel(child: EmptyState(icon: Icons.construction_outlined, title: '$title is not built yet', message: message));
}

class _NotConnected extends StatelessWidget {
  const _NotConnected({required this.title, required this.message});
  final String title, message;
  @override
  Widget build(BuildContext context) => Panel(child: EmptyState(icon: Icons.cable_outlined, title: '$title: data source not connected', message: message));
}

Widget _kv(String k, String v) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(children: [Expanded(child: Text(k, style: AppText.sans(size: 13, color: Palette.inkSecondary))), Text(v, style: AppText.mono())]),
    );

// ------------------------------------------------------------------ returns

/// Return over [days] calendar days ending at the last bar, or null when the
/// series does not reach back that far (never extrapolated).
double? returnOver(List<(DateTime, double)> series, int days) {
  if (series.length < 2) return null;
  final last = series.last;
  final target = last.$1.subtract(Duration(days: days));
  if (series.first.$1.isAfter(target.add(const Duration(days: 6)))) return null; // history too short
  (DateTime, double)? base;
  for (final p in series) {
    if (!p.$1.isAfter(target)) base = p;
  }
  base ??= series.first;
  if (base.$2 == 0) return null;
  return (last.$2 / base.$2 - 1) * 100;
}

List<(DateTime, double)> parseSeries(Json history) => [
      for (final r in asList(history['data']).map(asMap))
        if (DateTime.tryParse(r['date'].toString()) != null && asNum(r['close']) != null) (DateTime.parse(r['date'].toString()), asNum(r['close'])!)
    ];

// ----------------------------------------------------------------- overview

class OverviewTab extends StatelessWidget {
  const OverviewTab({super.key, required this.ticker, required this.analysis});
  final String ticker;
  final Json analysis;

  @override
  Widget build(BuildContext context) {
    final det = asMap(analysis['details']);
    final rec = asMap(analysis['recommendation']);
    final chart = asList(analysis['chart_data']).map(asMap).toList();
    final pts = [for (var i = 0; i < chart.length; i++) FlSpot(i.toDouble(), asNum(chart[i]['close']) ?? 0)];
    final sent = asMap(analysis['sentiment']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      FutureBuilder<List<Json>>(
        future: Future.wait([
          getJson('/api/stocks/history${queryString({'ticker': ticker, 'period': '1y', 'interval': '1d'})}').then(asMap),
          getJson('/api/stocks/history${queryString({'ticker': ticker, 'period': 'max', 'interval': '1mo'})}').then(asMap),
        ]),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const Loading();
          if (snap.hasError) return Panel(title: 'Returns', child: ErrorState(snap.error!));
          final daily = parseSeries(snap.data![0]);
          final monthly = parseSeries(snap.data![1]);
          final windows = <(String, double?)>[
            ('1D', returnOver(daily, 1)),
            ('1W', returnOver(daily, 7)),
            ('1M', returnOver(daily, 30)),
            ('3M', returnOver(daily, 91)),
            ('1Y', returnOver(daily, 365)),
            ('3Y', returnOver(monthly, 365 * 3)),
            ('5Y', returnOver(monthly, 365 * 5)),
            ('10Y', returnOver(monthly, 365 * 10)),
          ];
          return Panel(
            title: 'Returns',
            child: Wrap(spacing: 28, runSpacing: 12, children: [
              for (final (label, v) in windows)
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(label, style: AppText.label()),
                  const SizedBox(height: 4),
                  Text(v == null ? 'n/a' : fmtPct(v), style: AppText.mono(size: 15, weight: FontWeight.w600, color: v == null ? Palette.inkMuted : deltaColor(v))),
                ]),
            ]),
          );
        },
      ),
      const SizedBox(height: 16),
      Panel(
        title: 'Price (1 month)',
        child: LineChartX(
          height: 260,
          yFormat: (v) => fmtNum(v, dp: 0),
          xFormat: (x) {
            final i = x.round();
            return i >= 0 && i < chart.length ? chartDateLabel(chart[i]['date']) : '';
          },
          series: [Series('Close', pts, Palette.primary, area: true)],
        ),
      ),
      const SizedBox(height: 16),
      FutureBuilder<Json>(
        future: getJson('/api/stocks/$ticker/fundamentals').then(asMap),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const Loading();
          if (snap.hasError) return Panel(title: 'Ratios & checklist', child: ErrorState(snap.error!));
          final f = asMap(asMap(snap.data)['fundamentals']);
          final card = asMap(asMap(snap.data)['scorecard']);
          final signals = asList(card['signals']).map(asMap).where((s) => s['available'] == true).toList();
          return ResponsiveGrid(columns: 2, children: [
            Panel(
              title: 'Key ratios',
              child: f['available'] == false
                  ? EmptyState(title: 'Ratios unavailable', message: (f['reason'] ?? '').toString())
                  : Column(children: [
                      _kv('Sector', '${f['sector'] ?? '-'}'),
                      _kv('Market cap', f['market_cap_cr'] == null ? '-' : '₹${fmtNum(asNum(f['market_cap_cr']), dp: 0)} Cr'),
                      _kv('P/E', fmtNum(asNum(f['pe_ratio']))),
                      _kv('ROCE', fmtPct(asNum(f['roce_pct']), sign: false)),
                      _kv('ROE', fmtPct(asNum(f['roe_pct']), sign: false)),
                      _kv('Dividend yield', fmtPct(asNum(f['dividend_yield_pct']), sign: false)),
                      _kv('Book value', fmtNum(asNum(f['book_value']))),
                      _kv('Pledged', fmtPct(asNum(f['pledged_pct']), sign: false)),
                      _kv('Source', '${f['source'] ?? '-'}'),
                    ]),
            ),
            Panel(
              title: 'Investment checklist',
              trailing: StatusPill('Score ${card['score'] ?? '-'}', tone: Tone.primary),
              child: signals.isEmpty
                  ? const EmptyState(title: 'No scored signals', message: 'The fundamentals source returned too little to score.')
                  : Column(children: [
                      for (final s in signals)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            StatusPill(
                              (asNum(s['score']) ?? 50) >= 60 ? 'Pass' : ((asNum(s['score']) ?? 50) < 40 ? 'Fail' : 'Watch'),
                              tone: (asNum(s['score']) ?? 50) >= 60 ? Tone.buy : ((asNum(s['score']) ?? 50) < 40 ? Tone.sell : Tone.hold),
                            ),
                            const SizedBox(width: 10),
                            Expanded(child: Text((s['reason'] ?? s['key']).toString(), style: AppText.sans(size: 13, color: Palette.ink, height: 1.4))),
                          ]),
                        ),
                    ]),
            ),
          ]);
        },
      ),
      const SizedBox(height: 16),
      ResponsiveGrid(columns: 2, children: [
        Panel(title: 'Verdict', child: Text((rec['interpretation'] ?? 'No interpretation returned.').toString(), style: AppText.sans(size: 14, color: Palette.ink, height: 1.5))),
        Panel(
          title: 'Day range & 52 week',
          child: Column(children: [
            _kv('Day high', fmtNum(asNum(det['day_high']))),
            _kv('Day low', fmtNum(asNum(det['day_low']))),
            _kv('52w high', fmtNum(asNum(det['fifty_two_week_high']))),
            _kv('52w low', fmtNum(asNum(det['fifty_two_week_low']))),
            _kv('Volume', fmtNum(asNum(det['volume']), dp: 0)),
          ]),
        ),
      ]),
      const SizedBox(height: 16),
      Panel(
        title: 'News sentiment',
        trailing: StatusPill((sent['desc'] ?? 'n/a').toString(), tone: (asNum(sent['compound']) ?? 0) > 0.05 ? Tone.buy : ((asNum(sent['compound']) ?? 0) < -0.05 ? Tone.sell : Tone.neutral)),
        child: asList(analysis['news']).isEmpty
            ? Text('No recent headlines.', style: AppText.sans(color: Palette.inkSecondary))
            : Column(children: [
                for (final n in asList(analysis['news']).map(asMap).take(8))
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(n['title'].toString(), style: AppText.sans(size: 14, weight: FontWeight.w500)),
                    subtitle: Text('${n['source'] ?? ''} · ${n['time'] ?? ''}', style: AppText.sans(size: 12, color: Palette.inkSecondary)),
                  ),
              ]),
      ),
    ]);
  }
}

// -------------------------------------------------------------- technicals

class TechnicalsTab extends StatelessWidget {
  const TechnicalsTab({super.key, required this.ticker, required this.analysis});
  final String ticker;
  final Json analysis;
  @override
  Widget build(BuildContext context) {
    final tech = asMap(analysis['technicals']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      ResponsiveGrid(children: [
        KpiCard(label: 'RSI (14)', value: fmtNum(asNum(tech['rsi']), dp: 1), caption: (tech['rsi_desc'] ?? '').toString()),
        KpiCard(label: 'Trend', value: (tech['trend'] ?? '-').toString()),
        KpiCard(label: 'SMA 50', value: fmtNum(asNum(tech['sma50']))),
        KpiCard(label: 'SMA 200', value: fmtNum(asNum(tech['sma200']))),
      ]),
      const SizedBox(height: 16),
      FutureBody<Json>(
        future: getJson('/api/stocks/$ticker/technicals').then(asMap),
        builder: (t) {
          final card = asMap(t['scorecard']);
          final signals = asList(card['signals']).map(asMap).where((s) => s['available'] == true).toList();
          return Panel(
            title: 'Signals',
            trailing: StatusPill('Score ${card['score'] ?? '-'}  ${card['action'] ?? ''}', tone: Tone.primary),
            padding: EdgeInsets.zero,
            child: DataTableX(
              columns: const ['Signal', 'Value', 'Score', 'Reading'],
              numericFrom: 1,
              rows: [
                for (final s in signals)
                  [
                    (s['key'] ?? '').toString().replaceAll('_', ' '),
                    s['value'] is num ? fmtNum(asNum(s['value'])) : '${s['value'] ?? '-'}',
                    fmtNum(asNum(s['score']), dp: 0),
                    Text((s['reason'] ?? '').toString(), style: AppText.sans(size: 12, color: Palette.inkSecondary)),
                  ]
              ],
            ),
          );
        },
      ),
    ]);
  }
}

// --------------------------------------------------------------- financials

/// 'Mar 2024' -> 'Mar 24'; anything else (e.g. 'TTM') is left as is.
String _shortPeriod(String p) => RegExp(r'^[A-Za-z]{3} \d{4}$').hasMatch(p) ? '${p.substring(0, 3)} ${p.substring(p.length - 2)}' : p;

String _cell(String label, double? v) {
  if (v == null) return '-';
  if (label.contains('%')) return '${v.toStringAsFixed(1)}%';
  return fmtNum(v, dp: v.abs() >= 100 ? 0 : 2);
}

/// A statement table (periods as columns). Tapping a row charts that row.
class StatementTable extends StatefulWidget {
  const StatementTable({super.key, required this.table, this.unit});
  final Json table;
  final String? unit;
  @override
  State<StatementTable> createState() => _StatementTableState();
}

class _StatementTableState extends State<StatementTable> {
  int? _row;
  @override
  Widget build(BuildContext context) {
    final periods = asList(widget.table['periods']).map((e) => e.toString()).toList();
    final rows = asList(widget.table['rows']).map(asMap).toList();
    if (rows.isEmpty) return const EmptyState(title: 'No rows for this statement');
    final r = _row == null ? null : rows[_row!];
    final vals = r == null ? <double?>[] : asList(r['values']).map(asNum).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (r != null) ...[
        Padding(
          padding: const EdgeInsets.all(14),
          child: LineChartX(
            height: 200,
            yFormat: (v) => fmtNum(v, dp: v.abs() >= 100 ? 0 : 1),
            xFormat: (x) {
              final i = x.round();
              return i >= 0 && i < periods.length ? _shortPeriod(periods[i]) : '';
            },
            series: [
              Series(
                r['label'].toString(),
                [for (var i = 0; i < vals.length; i++) if (vals[i] != null) FlSpot(i.toDouble(), vals[i]!)],
                Palette.primary,
                area: true,
              ),
            ],
          ),
        ),
        const Divider(),
      ],
      DataTableX(
        columns: [widget.unit ?? '', ...periods],
        numericFrom: 1,
        onRowTap: (i) => setState(() => _row = _row == i ? null : i),
        rows: [
          for (final row in rows) [row['label'], for (final v in asList(row['values']).map(asNum)) _cell(row['label'].toString(), v)]
        ],
      ),
    ]);
  }
}

class FinancialsTab extends StatefulWidget {
  const FinancialsTab({super.key, required this.ticker});
  final String ticker;
  @override
  State<FinancialsTab> createState() => _FinancialsTabState();
}

class _FinancialsTabState extends State<FinancialsTab> {
  static const _sections = [('Quarterly results', 'quarterly_results'), ('Profit & loss', 'profit_loss'), ('Balance sheet', 'balance_sheet'), ('Cash flow', 'cash_flow'), ('Ratios', 'ratios')];
  int _i = 0;
  late final Future<Json> _data = getJson('/api/stocks/${widget.ticker}/financials').then(asMap);

  @override
  Widget build(BuildContext context) {
    return FutureBody<Json>(
      future: _data,
      builder: (d) {
        if (d['available'] == false) {
          return Panel(child: EmptyState(icon: Icons.cable_outlined, title: 'Financials unavailable', message: (d['reason'] ?? '').toString()));
        }
        final t = d[_sections[_i].$2];
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SegTabs(labels: [for (final s in _sections) s.$1], index: _i, onChanged: (i) => setState(() => _i = i)),
          const SizedBox(height: 14),
          Panel(
            title: _sections[_i].$1,
            trailing: Text('${d['unit'] ?? ''} · ${d['source'] ?? ''} · tap a row to chart it', style: AppText.sans(size: 12, color: Palette.inkSecondary)),
            padding: EdgeInsets.zero,
            child: t == null ? const EmptyState(title: 'Not reported for this company') : StatementTable(table: asMap(t), unit: _i == 4 ? null : 'INR crore'),
          ),
        ]);
      },
    );
  }
}

// ------------------------------------------------------------- shareholding

class ShareholdingTab extends StatefulWidget {
  const ShareholdingTab({super.key, required this.ticker});
  final String ticker;
  @override
  State<ShareholdingTab> createState() => _ShareholdingTabState();
}

class _ShareholdingTabState extends State<ShareholdingTab> {
  int _view = 0;
  late final Future<Json> _data = getJson('/api/stocks/${widget.ticker}/shareholding').then(asMap);
  static const _colors = [Palette.primary, Palette.buy, Palette.hold, Palette.sell, Palette.inkSecondary, Palette.inkMuted];

  @override
  Widget build(BuildContext context) {
    return FutureBody<Json>(
      future: _data,
      builder: (d) {
        if (d['available'] == false) {
          return Panel(child: EmptyState(icon: Icons.cable_outlined, title: 'Shareholding unavailable', message: (d['reason'] ?? '').toString()));
        }
        final t = asMap(d[_view == 0 ? 'quarterly' : 'yearly']);
        final periods = asList(t['periods']).map((e) => e.toString()).toList();
        // "No. of Shareholders" is a head-count, not a percentage: keep it in the table, out of the chart.
        final pctRows = asList(t['rows']).map(asMap).where((r) => !r['label'].toString().toLowerCase().contains('no. of')).toList();
        final latest = [for (final r in pctRows) (r['label'].toString(), asList(r['values']).map(asNum).lastWhere((v) => v != null, orElse: () => null))];
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SegTabs(labels: const ['Quarterly', 'Yearly'], index: _view, onChanged: (i) => setState(() => _view = i)),
          const SizedBox(height: 14),
          if (latest.isNotEmpty)
            ResponsiveGrid(columns: 4, children: [for (final (label, v) in latest.take(4)) KpiCard(label: label, value: v == null ? '-' : fmtPct(v, sign: false))]),
          const SizedBox(height: 14),
          Panel(
            title: 'Holding over time (%)',
            child: LineChartX(
              height: 260,
              yFormat: (v) => '${v.toStringAsFixed(0)}%',
              xFormat: (x) {
                final i = x.round();
                return i >= 0 && i < periods.length ? periods[i] : '';
              },
              series: [
                for (var k = 0; k < pctRows.length; k++)
                  Series(
                    pctRows[k]['label'].toString(),
                    [for (var i = 0; i < asList(pctRows[k]['values']).length; i++) if (asNum(asList(pctRows[k]['values'])[i]) != null) FlSpot(i.toDouble(), asNum(asList(pctRows[k]['values'])[i])!)],
                    _colors[k % _colors.length],
                  ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Panel(
            title: 'Shareholding pattern',
            padding: EdgeInsets.zero,
            child: StatementTable(table: t, unit: ''),
          ),
        ]);
      },
    );
  }
}
