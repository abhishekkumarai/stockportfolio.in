import 'package:fl_chart/fl_chart.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api/http_client.dart';
import '../../core/theme.dart';
import '../../widgets/charts.dart';
import '../../widgets/common.dart';
import 'portfolio_store.dart';

/// Wraps a portfolio page: loads the store, shows the empty-portfolio notice
/// (no sample numbers) or the loading / error state, else builds [builder].
class PortfolioGate extends StatefulWidget {
  const PortfolioGate({super.key, required this.title, this.subtitle, required this.builder, this.needsAnalysis = true, this.actions = const []});
  final String title;
  final String? subtitle;
  final Widget Function(BuildContext, PortfolioStore) builder;
  final bool needsAnalysis;
  final List<Widget> actions;
  @override
  State<PortfolioGate> createState() => _PortfolioGateState();
}

class _PortfolioGateState extends State<PortfolioGate> {
  @override
  void initState() {
    super.initState();
    portfolioStore.ensureLoaded();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: portfolioStore,
      builder: (context, _) {
        final s = portfolioStore;
        Widget body;
        if (s.portfolio.isEmpty) {
          body = EmptyState(
            icon: Icons.account_balance_wallet_outlined,
            title: 'No holdings yet',
            message: 'Add holdings, import from Fyers or upload a broker statement. Nothing is shown until real positions exist.',
            action: FilledButton(onPressed: () => context.go('/portfolio/holdings'), child: const Text('Add holdings')),
          );
        } else if (widget.needsAnalysis && s.loading && s.valuation == null) {
          body = const Loading();
        } else if (widget.needsAnalysis && s.error != null && s.valuation == null) {
          body = ErrorState(s.error!, onRetry: s.refresh);
        } else {
          body = widget.builder(context, s);
        }
        return PageScaffold(title: widget.title, subtitle: widget.subtitle, actions: widget.actions, children: [body]);
      },
    );
  }
}

String _money(dynamic v) => fmtInr(asNum(v));

// ---------------------------------------------------------------- overview

class PortfolioOverviewPage extends StatelessWidget {
  const PortfolioOverviewPage({super.key});
  @override
  Widget build(BuildContext context) => PortfolioGate(
        title: 'Wealth Cone & VaR',
        subtitle: 'Projected range of outcomes and what your book can lose in a bad month.',
        builder: (context, s) => PortfolioOverviewBody(store: s),
      );
}

class PortfolioOverviewBody extends StatelessWidget {
  const PortfolioOverviewBody({super.key, required this.store});
  final PortfolioStore store;

  @override
  Widget build(BuildContext context) {
    final v = store.valuation ?? {};
    final totals = asMap(v['totals']);
    final danger = asMap(store.danger);
    final metrics = asMap(danger['metrics']);
    final growth = asMap(store.growth);
    final mc = asMap(growth['monte_carlo']);
    final summary = asMap(mc['summary']);
    final traj = asList(mc['trajectory']).map(asMap).toList();
    final alloc = asMap(v['allocation']);

    List<FlSpot> line(String k) => [for (final t in traj) FlSpot((asNum(t['month']) ?? 0) / 12, asNum(t[k]) ?? 0)];

    List<(String, double)> slices(String k) =>
        [for (final s in asList(alloc[k])) (asMap(s)['label'].toString(), asNum(asMap(s)['weight_pct']) ?? 0)];

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      ResponsiveGrid(children: [
        KpiCard(label: 'Current value', value: _money(totals['current_value']), delta: asNum(totals['pnl_pct'])),
        KpiCard(label: 'Invested', value: _money(totals['invested'])),
        KpiCard(label: 'Unrealised P&L', value: _money(totals['pnl'])),
        KpiCard(label: 'Holdings priced', value: '${totals['priced'] ?? 0} / ${totals['holdings'] ?? 0}'),
      ]),
      const SizedBox(height: 16),
      ResponsiveGrid(children: [
        KpiCard(label: 'Danger score', value: '${danger['danger_score'] ?? '-'}', caption: (danger['danger_level'] ?? '').toString()),
        KpiCard(label: 'Monthly VaR 95%', value: fmtPct(asNum(metrics['monthly_var_95_pct']), sign: false), caption: 'CVaR ${fmtPct(asNum(metrics['monthly_cvar_95_pct']), sign: false)}'),
        KpiCard(label: 'Portfolio beta', value: fmtNum(asNum(metrics['portfolio_beta']))),
        KpiCard(label: 'Top 3 weight', value: fmtPct(asNum(metrics['top3_weight_pct']), sign: false), caption: 'HHI ${fmtNum(asNum(metrics['hhi']))}'),
      ]),
      const SizedBox(height: 24),
      Panel(
        title: 'Wealth cone (Monte Carlo, 5 years)',
        child: traj.isEmpty
            ? const EmptyState(title: 'No projection available')
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                LineChartX(
                  height: 300,
                  yFormat: (v) => fmtInr(v),
                  xFormat: (x) => '${x.toStringAsFixed(0)}y',
                  series: [
                    Series('P90', line('p90_inr'), Palette.buy.withValues(alpha: 0.5), dashed: true, width: 1.5),
                    Series('P75', line('p75_inr'), Palette.buy, width: 1.5),
                    Series('Median', line('median_inr'), Palette.primary, width: 2.5),
                    Series('P25', line('p25_inr'), Palette.hold, width: 1.5),
                    Series('P10', line('p10_inr'), Palette.sell, dashed: true, width: 1.5),
                  ],
                ),
                const SizedBox(height: 16),
                Wrap(spacing: 28, runSpacing: 10, children: [
                  _fact('Year 1 median', _money(summary['year_1_median_inr'])),
                  _fact('Year 3 median', _money(summary['year_3_median_inr'])),
                  _fact('Year 5 median', _money(summary['year_5_median_inr'])),
                  _fact('P(double in 5y)', fmtPct(asNum(summary['prob_doubling_5y_pct']), sign: false)),
                  _fact('P(loss in 5y)', fmtPct(asNum(summary['prob_loss_5y_pct']), sign: false)),
                  _fact('Expected CAGR', fmtPct(asNum(summary['expected_cagr_pct']), sign: false)),
                ]),
              ]),
      ),
      const SizedBox(height: 16),
      ResponsiveGrid(columns: 3, children: [
        Panel(title: 'By sector', child: WeightBars(slices: slices('sector'))),
        Panel(title: 'By market cap', child: WeightBars(slices: slices('cap'))),
        Panel(title: 'By asset class', child: WeightBars(slices: slices('asset_class'))),
      ]),
      const SizedBox(height: 16),
      Panel(
        title: 'Risk flags',
        child: asList(danger['flags']).isEmpty
            ? Text('No concentration or risk flags raised.', style: AppText.sans(color: Palette.inkSecondary))
            : Column(children: [
                for (final f in asList(danger['flags']).map(asMap))
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: StatusPill(f['severity'].toString(),
                        tone: f['severity'] == 'CRITICAL' ? Tone.sell : (f['severity'] == 'WARNING' ? Tone.hold : Tone.neutral)),
                    title: Text(f['title'].toString(), style: AppText.sans(weight: FontWeight.w600)),
                    subtitle: Text(f['detail'].toString(), style: AppText.sans(size: 13, color: Palette.inkSecondary)),
                  ),
              ]),
      ),
    ]);
  }

  Widget _fact(String k, String v) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(k.toUpperCase(), style: AppText.label()),
        const SizedBox(height: 4),
        Text(v, style: AppText.mono(size: 15, weight: FontWeight.w600)),
      ]);
}

// ---------------------------------------------------------------- holdings

class HoldingsPage extends StatefulWidget {
  const HoldingsPage({super.key});
  @override
  State<HoldingsPage> createState() => _HoldingsPageState();
}

class _HoldingsPageState extends State<HoldingsPage> {
  final _symbol = TextEditingController();
  final _qty = TextEditingController();
  final _cost = TextEditingController();
  final _date = TextEditingController();
  final _cash = TextEditingController();
  String? _msg;
  String? _err;

  @override
  void initState() {
    super.initState();
    portfolioStore.ensureLoaded();
    _cash.text = portfolioStore.portfolio.cash == 0 ? '' : portfolioStore.portfolio.cash.toString();
  }

  Future<void> _add() async {
    final q = double.tryParse(_qty.text), c = double.tryParse(_cost.text);
    if (_symbol.text.trim().isEmpty || q == null || c == null || q <= 0 || c < 0) {
      setState(() => _err = 'Enter a symbol, a positive quantity and an average cost.');
      return;
    }
    setState(() => _err = null);
    await portfolioStore.addEquity(_symbol.text, q, c, _date.text);
    _symbol.clear();
    _qty.clear();
    _cost.clear();
    _date.clear();
  }

  Future<void> _upload() async {
    setState(() {
      _msg = null;
      _err = null;
    });
    final f = await FilePicker.pickFile(type: FileType.custom, allowedExtensions: ['xlsx', 'xls', 'csv']);
    if (f == null) return;
    try {
      final m = await portfolioStore.uploadStatement(f.name, await f.readAsBytes());
      setState(() => _msg = m);
    } catch (e) {
      setState(() => _err = e.toString());
    }
  }

  Future<void> _fyers() async {
    try {
      final r = await fyersHoldings();
      final list = asList(r['holdings']).map(asMap).toList();
      if (list.isEmpty) {
        setState(() => _err = 'Fyers returned no holdings.');
        return;
      }
      final p = StoredPortfolio(cash: portfolioStore.portfolio.cash, funds: portfolioStore.portfolio.funds, equity: [
        for (final h in list)
          {'symbol': h['symbol'], 'quantity': h['quantity'], 'avg_cost': h['avg_cost'], if (h['buy_date'] != null) 'buy_date': h['buy_date']}
      ]);
      await portfolioStore.save(p);
      setState(() => _msg = 'Imported ${list.length} holdings from Fyers.');
    } catch (e) {
      setState(() => _err = 'Fyers: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: portfolioStore,
      builder: (context, _) {
        final s = portfolioStore;
        final priced = [for (final r in asList(s.valuation?['holdings']).map(asMap)) r];
        return PageScaffold(
          title: 'Holdings',
          subtitle: 'Stored on this device. Valued against live prices by the backend.',
          actions: [
            OutlinedButton.icon(onPressed: _upload, icon: const Icon(Icons.upload_file, size: 18), label: const Text('Upload statement')),
            OutlinedButton.icon(onPressed: _fyers, icon: const Icon(Icons.sync, size: 18), label: const Text('Import from Fyers')),
          ],
          children: [
            if (_msg != null) _banner(_msg!, Palette.buy, Palette.buySurface),
            if (_err != null) _banner(_err!, Palette.sell, Palette.sellSurface),
            Panel(
              title: 'Add an equity holding',
              child: Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.end, children: [
                _field(_symbol, 'Symbol (e.g. RELIANCE)', 200),
                _field(_qty, 'Quantity', 120, number: true),
                _field(_cost, 'Avg cost (₹)', 140, number: true),
                _field(_date, 'Buy date (YYYY-MM-DD)', 190),
                FilledButton(onPressed: _add, child: const Text('Add')),
              ]),
            ),
            const SizedBox(height: 16),
            Panel(
              title: 'Cash',
              child: Row(children: [
                _field(_cash, 'Cash balance (₹)', 200, number: true),
                const SizedBox(width: 12),
                OutlinedButton(onPressed: () => s.setCash(double.tryParse(_cash.text) ?? 0), child: const Text('Save')),
              ]),
            ),
            const SizedBox(height: 16),
            Panel(
              title: 'Positions',
              padding: const EdgeInsets.all(0),
              child: s.portfolio.isEmpty
                  ? const EmptyState(title: 'No holdings yet', message: 'Add one above, upload a statement, or import from Fyers.')
                  : s.loading && priced.isEmpty
                      ? const Loading()
                      : DataTableX(
                          columns: const ['Holding', 'Qty', 'Avg cost', 'Price', 'Value', 'P&L %', 'Weight', ''],
                          rows: [
                            for (var i = 0; i < priced.length; i++)
                              [
                                priced[i]['name'] ?? priced[i]['key'],
                                fmtNum(asNum(priced[i]['quantity']), dp: 2),
                                fmtNum(asNum(priced[i]['avg_cost'])),
                                fmtNum(asNum(priced[i]['price'])),
                                fmtInr(asNum(priced[i]['current_value'])),
                                _pnl(asNum(priced[i]['pnl_pct'])),
                                fmtPct(asNum(priced[i]['weight_pct']), sign: false),
                                _remove(priced[i]),
                              ]
                          ],
                        ),
            ),
          ],
        );
      },
    );
  }

  Widget _pnl(double? v) => Text(fmtPct(v), style: AppText.mono(size: 13, color: deltaColor(v)));

  Widget _remove(Json row) => IconButton(
        tooltip: 'Remove',
        icon: const Icon(Icons.delete_outline, size: 18, color: Palette.inkMuted),
        onPressed: () {
          final key = row['key'].toString();
          final eq = portfolioStore.portfolio.equity.indexWhere((e) => e['symbol'].toString() == key);
          if (eq >= 0) {
            portfolioStore.removeEquity(eq);
            return;
          }
          final fd = portfolioStore.portfolio.funds.indexWhere((e) => e['scheme_code'].toString() == key);
          if (fd >= 0) portfolioStore.removeFund(fd);
        },
      );

  Widget _banner(String text, Color fg, Color bg) => Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(12),
        width: double.infinity,
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(8)),
        child: Text(text, style: AppText.sans(size: 13, color: fg)),
      );

  Widget _field(TextEditingController c, String label, double w, {bool number = false}) => SizedBox(
        width: w,
        child: TextField(
          controller: c,
          keyboardType: number ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
          decoration: InputDecoration(labelText: label),
        ),
      );
}

// ------------------------------------------------------------------ stress

class StressPage extends StatelessWidget {
  const StressPage({super.key});
  @override
  Widget build(BuildContext context) => PortfolioGate(
        title: 'Crash Simulator',
        subtitle: 'Historical crises replayed on your actual holdings using their beta.',
        builder: (context, s) {
          final tests = asList(asMap(s.danger)['stress_tests']).map(asMap).toList();
          if (tests.isEmpty) return const EmptyState(title: 'No stress scenarios returned');
          return Column(children: [
            for (final t in tests)
              Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Panel(
                  title: t['name'].toString(),
                  trailing: StatusPill('Market ${fmtPct(asNum(t['benchmark_drop_pct']), sign: false)}', tone: Tone.sell),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(t['description'].toString(), style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.45)),
                    const SizedBox(height: 14),
                    Wrap(spacing: 32, runSpacing: 10, children: [
                      _kv('Projected drawdown', fmtPct(asNum(t['projected_drawdown_pct']), sign: false), Palette.sell),
                      _kv('Projected loss', fmtInr(asNum(t['projected_loss_inr'])), Palette.sell),
                      _kv('Effective beta', fmtNum(asNum(t['effective_beta']))),
                      _kv('Value after', fmtInr(asNum(t['projected_recovery_value']))),
                    ]),
                  ]),
                ),
              ),
          ]);
        },
      );
}

Widget _kv(String k, String v, [Color c = Palette.ink]) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(k.toUpperCase(), style: AppText.label()),
      const SizedBox(height: 4),
      Text(v, style: AppText.mono(size: 15, weight: FontWeight.w600, color: c)),
    ]);

// --------------------------------------------------------------- rebalance

class RebalancePage extends StatefulWidget {
  const RebalancePage({super.key});
  @override
  State<RebalancePage> createState() => _RebalancePageState();
}

class _RebalancePageState extends State<RebalancePage> {
  final _inflow = TextEditingController(text: '0');
  String _mode = 'zero_tax_inflow';
  Future<Json>? _plan;

  void _run() => setState(() => _plan = rebalance(portfolioStore.portfolio,
      cashInflow: double.tryParse(_inflow.text) ?? 0, mode: _mode));

  @override
  Widget build(BuildContext context) => PortfolioGate(
        title: 'Tax Rebalance',
        subtitle: 'An order sheet that accounts for STCG, LTCG and routes fresh cash before selling.',
        needsAnalysis: false,
        builder: (context, s) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Panel(
            child: Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.end, children: [
              SizedBox(width: 200, child: TextField(controller: _inflow, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Fresh cash (₹)'))),
              SegTabs(
                labels: const ['Zero-tax inflow', 'Full rebalance'],
                index: _mode == 'zero_tax_inflow' ? 0 : 1,
                onChanged: (i) => setState(() => _mode = i == 0 ? 'zero_tax_inflow' : 'full_rebalance'),
              ),
              FilledButton(onPressed: _run, child: const Text('Build order sheet')),
            ]),
          ),
          const SizedBox(height: 16),
          if (_plan != null)
            FutureBody<Json>(
              future: _plan!,
              builder: (p) {
                final orders = asList(p['orders']).map(asMap).toList();
                final tax = asMap(p['tax_summary']);
                return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  ResponsiveGrid(children: [
                    KpiCard(label: 'Estimated tax', value: fmtInr(asNum(tax['total_tax_inr'] ?? tax['total_estimated_tax_inr']))),
                    KpiCard(label: 'Loss harvested', value: fmtInr(asNum(tax['tax_loss_harvest_generated_inr']))),
                    KpiCard(label: 'Net tax', value: fmtInr(asNum(tax['net_effective_tax_inr']))),
                    KpiCard(label: 'Cash remaining', value: fmtInr(asNum(p['cash_remaining_inr']))),
                  ]),
                  const SizedBox(height: 16),
                  Panel(
                    title: 'Orders',
                    padding: EdgeInsets.zero,
                    child: DataTableX(
                      columns: const ['Name', 'Action', 'Units', 'Price', 'Amount', 'Tax impact', 'Reason'],
                      numericFrom: 2,
                      rows: [
                        for (final o in orders)
                          [
                            o['name'],
                            StatusPill(o['action'].toString(),
                                tone: o['action'] == 'BUY' ? Tone.buy : (o['action'] == 'TRIM' ? Tone.sell : Tone.hold)),
                            fmtNum(asNum(o['units']), dp: 2),
                            fmtNum(asNum(o['estimated_price'])),
                            fmtInr(asNum(o['estimated_amount'])),
                            fmtInr(asNum(o['tax_impact_inr'])),
                            o['reason'],
                          ]
                      ],
                    ),
                  ),
                  if (asList(p['notes']).isNotEmpty) ...[
                    const SizedBox(height: 12),
                    for (final n in asList(p['notes'])) Text('• $n', style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.5)),
                  ],
                ]);
              },
            ),
        ]),
      );
}

// -------------------------------------------------------------------- news

class NewsPage extends StatelessWidget {
  const NewsPage({super.key});
  @override
  Widget build(BuildContext context) => PortfolioGate(
        title: 'Catalysts & News',
        subtitle: 'Headlines for the companies and funds you hold, tagged by likely impact.',
        needsAnalysis: false,
        builder: (context, s) => FutureBody<Json>(
          future: portfolioNews(s.portfolio),
          builder: (r) {
            final items = asList(r['articles']).map(asMap).toList();
            if (items.isEmpty) return const EmptyState(title: 'No recent news for your holdings');
            return Panel(
              padding: const EdgeInsets.all(0),
              child: Column(children: [
                for (final a in items)
                  ListTile(
                    onTap: () => launchUrl(Uri.parse(a['url'].toString())),
                    title: Text(a['title'].toString(), style: AppText.sans(weight: FontWeight.w600)),
                    subtitle: Text('${a['symbol'] ?? a['scheme_name'] ?? ''} · ${a['source'] ?? ''} · ${a['published_at'] ?? ''}',
                        style: AppText.sans(size: 12, color: Palette.inkSecondary)),
                    trailing: StatusPill((a['impact_label'] ?? a['impact']).toString(),
                        tone: a['impact'] == 'BULLISH' ? Tone.buy : (a['impact'] == 'BEARISH' ? Tone.sell : Tone.neutral)),
                  ),
              ]),
            );
          },
        ),
      );
}

// -------------------------------------------------------------------- memo

class MemoPage extends StatefulWidget {
  const MemoPage({super.key});
  @override
  State<MemoPage> createState() => _MemoPageState();
}

class _MemoPageState extends State<MemoPage> {
  Future<Json>? _report;
  bool _news = true;

  void _run() => setState(() => _report = postJson('/api/ai/report', {
        'portfolio': {
          'equity': portfolioStore.portfolio.equity,
          'funds': portfolioStore.portfolio.funds,
          'cash': portfolioStore.portfolio.cash
        },
        'period_label': null,
        'include_news': _news,
        'effort': 'medium',
      }).then(asMap));

  @override
  Widget build(BuildContext context) => PortfolioGate(
        title: 'AI Memo',
        subtitle: 'A written monthly review. The narrator only restates computed figures; unsupported numbers are listed.',
        needsAnalysis: false,
        builder: (context, s) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            FilledButton(onPressed: _run, child: const Text('Generate memo')),
            const SizedBox(width: 16),
            Switch(value: _news, onChanged: (v) => setState(() => _news = v)),
            Text('Include news', style: AppText.sans(size: 13)),
          ]),
          const SizedBox(height: 16),
          if (_report != null)
            FutureBody<Json>(
              future: _report!,
              builder: (r) {
                if (r['available'] == false) {
                  return EmptyState(icon: Icons.info_outline, title: 'Memo unavailable', message: (r['reason'] ?? 'The AI service is not configured.').toString());
                }
                final unsupported = asList(r['unsupported_figures']);
                return Panel(
                  title: r['period']?.toString() ?? 'Monthly memo',
                  trailing: StatusPill((r['verification'] ?? 'unverified').toString(), tone: unsupported.isEmpty ? Tone.buy : Tone.hold),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    SelectableText((r['report_markdown'] ?? '').toString(), style: AppText.sans(size: 14, color: Palette.ink, height: 1.6)),
                    if (unsupported.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      Text('Figures the checker could not support: ${unsupported.join(', ')}',
                          style: AppText.sans(size: 12, color: Palette.hold)),
                    ],
                  ]),
                );
              },
            ),
        ]),
      );
}
