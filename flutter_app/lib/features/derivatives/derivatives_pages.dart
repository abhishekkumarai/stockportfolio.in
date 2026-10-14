import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../core/api/http_client.dart';
import '../../core/theme.dart';
import '../../widgets/charts.dart';
import '../../widgets/common.dart';
import '../portfolio/portfolio_store.dart';

Widget _field(TextEditingController c, String label, double w, {bool number = true}) => SizedBox(
      width: w,
      child: TextField(
        controller: c,
        keyboardType: number ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
        decoration: InputDecoration(labelText: label),
      ),
    );

Widget _kv(String k, String v, [Color c = Palette.ink]) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(k.toUpperCase(), style: AppText.label()),
      const SizedBox(height: 4),
      Text(v, style: AppText.mono(size: 15, weight: FontWeight.w600, color: c)),
    ]);

// ---------------------------------------------------------------- options

class OptionsPage extends StatefulWidget {
  const OptionsPage({super.key});
  @override
  State<OptionsPage> createState() => _OptionsPageState();
}

class _OptionsPageState extends State<OptionsPage> {
  String _symbol = 'NIFTY';
  late Future<Json> _data = _load();
  Future<Json> _load() => getJson('/api/options/$_symbol/analysis${queryString({'strike_count': 12})}').then(asMap);

  Tone _buildTone(String? b) => switch (b) {
        'long_buildup' || 'short_covering' => Tone.buy,
        'short_buildup' => Tone.sell,
        'long_unwinding' => Tone.hold,
        _ => Tone.neutral,
      };

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Options Chain & OI',
      subtitle: 'Put-call ratio, max pain, open-interest walls and build-up for an index chain.',
      actions: [
        SegTabs(
          labels: const ['NIFTY', 'BANKNIFTY', 'FINNIFTY'],
          index: ['NIFTY', 'BANKNIFTY', 'FINNIFTY'].indexOf(_symbol),
          onChanged: (i) => setState(() {
            _symbol = ['NIFTY', 'BANKNIFTY', 'FINNIFTY'][i];
            _data = _load();
          }),
        ),
      ],
      children: [
        FutureBody<Json>(
          future: _data,
          builder: (a) {
            if (a['available'] == false) {
              return EmptyState(title: 'Chain unavailable', message: (a['reason'] ?? 'The broker session may need to be connected.').toString());
            }
            final ctx = asMap(a['context']);
            final pcr = asMap(a['pcr']);
            final mp = asMap(a['max_pain']);
            final walls = asMap(a['oi_walls']);
            final build = asList(a['buildup']).map(asMap).toList();
            final iv = asMap(a['iv']);
            final curve = asList(mp['pain_curve']).map(asMap).toList();
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ResponsiveGrid(children: [
                KpiCard(label: 'Spot', value: fmtNum(asNum(ctx['spot']))),
                KpiCard(label: 'OI PCR', value: fmtNum(asNum(pcr['oi_pcr'])), caption: (pcr['interpretation'] ?? '').toString()),
                KpiCard(label: 'Max pain', value: fmtNum(asNum(mp['max_pain_strike']), dp: 0)),
                KpiCard(label: 'India VIX', value: fmtNum(asNum(ctx['india_vix']))),
              ]),
              const SizedBox(height: 16),
              ResponsiveGrid(columns: 2, children: [
                Panel(
                  title: 'Resistance (call OI walls)',
                  padding: EdgeInsets.zero,
                  child: DataTableX(columns: const ['Strike', 'OI', 'OI change'], rows: [
                    for (final w in asList(walls['resistance']).map(asMap)) [fmtNum(asNum(w['strike']), dp: 0), fmtNum(asNum(w['oi']), dp: 0), fmtNum(asNum(w['oi_change']), dp: 0)]
                  ]),
                ),
                Panel(
                  title: 'Support (put OI walls)',
                  padding: EdgeInsets.zero,
                  child: DataTableX(columns: const ['Strike', 'OI', 'OI change'], rows: [
                    for (final w in asList(walls['support']).map(asMap)) [fmtNum(asNum(w['strike']), dp: 0), fmtNum(asNum(w['oi']), dp: 0), fmtNum(asNum(w['oi_change']), dp: 0)]
                  ]),
                ),
              ]),
              const SizedBox(height: 16),
              Panel(
                title: 'Max pain curve',
                child: LineChartX(
                  height: 240,
                  yFormat: (v) => fmtNum(v / 1e7, dp: 1),
                  xFormat: (x) => fmtNum(x, dp: 0),
                  series: [Series('Total pain (₹ Cr)', [for (final c in curve) FlSpot(asNum(c['strike']) ?? 0, asNum(c['total_pain']) ?? 0)], Palette.primary)],
                ),
              ),
              if (iv['available'] == true) ...[
                const SizedBox(height: 16),
                Panel(
                  title: 'Implied volatility',
                  child: Wrap(spacing: 32, runSpacing: 10, children: [
                    _kv('ATM IV', fmtPct(asNum(iv['atm_iv_pct']), sign: false)),
                    _kv('OTM put IV', fmtPct(asNum(iv['otm_put_iv_pct']), sign: false)),
                    _kv('OTM call IV', fmtPct(asNum(iv['otm_call_iv_pct']), sign: false)),
                    _kv('Skew', fmtPct(asNum(iv['skew_pct']))),
                  ]),
                ),
              ],
              const SizedBox(height: 16),
              Panel(
                title: 'OI build-up',
                padding: EdgeInsets.zero,
                child: DataTableX(
                  columns: const ['Strike', 'Type', 'LTP', 'OI', 'OI change', 'Build-up'],
                  numericFrom: 2,
                  rows: [
                    for (final b in build)
                      [
                        fmtNum(asNum(b['strike']), dp: 0),
                        b['option_type'],
                        fmtNum(asNum(b['ltp'])),
                        fmtNum(asNum(b['oi']), dp: 0),
                        fmtNum(asNum(b['oi_change']), dp: 0),
                        StatusPill((b['buildup_label'] ?? b['buildup']).toString(), tone: _buildTone(b['buildup']?.toString())),
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

// -------------------------------------------------------------- tail risk

class TailRiskPage extends StatefulWidget {
  const TailRiskPage({super.key});
  @override
  State<TailRiskPage> createState() => _TailRiskPageState();
}

class _TailRiskPageState extends State<TailRiskPage> {
  final _spot = TextEditingController();
  final _value = TextEditingController();
  final _beta = TextEditingController(text: '1.0');
  final _dd = TextEditingController(text: '10');
  final _cap = TextEditingController(text: '8');
  String _strategy = 'protective_put';
  Future<Json>? _plan;

  @override
  void initState() {
    super.initState();
    portfolioStore.ensureLoaded();
  }

  void _run() {
    final spot = double.tryParse(_spot.text), value = double.tryParse(_value.text);
    if (spot == null || value == null) return;
    setState(() => _plan = postJson('/api/options/hedge', {
          'portfolio_value': value,
          'portfolio_beta': double.tryParse(_beta.text) ?? 1.0,
          'index_spot': spot,
          'strategy': _strategy,
          'target_max_drawdown': (double.tryParse(_dd.text) ?? 10) / 100,
          if (_strategy == 'collar') 'upside_cap': (double.tryParse(_cap.text) ?? 8) / 100,
        }).then(asMap));
  }

  @override
  Widget build(BuildContext context) {
    final val = asNum(asMap(portfolioStore.valuation?['totals'])['current_value']);
    return PageScaffold(
      title: 'Tail Risk Sizer',
      subtitle: 'How many index put contracts, or what collar, cap a portfolio drawdown at your limit.',
      children: [
        Panel(
          child: Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.end, children: [
            _field(_spot, 'Index spot', 140),
            _field(_value, val == null ? 'Portfolio value (₹)' : 'Portfolio value (₹) — yours ${fmtInr(val)}', 260),
            _field(_beta, 'Beta', 90),
            _field(_dd, 'Max drawdown %', 140),
            if (_strategy == 'collar') _field(_cap, 'Upside cap %', 120),
            SegTabs(labels: const ['Protective put', 'Collar'], index: _strategy == 'collar' ? 1 : 0, onChanged: (i) => setState(() => _strategy = i == 0 ? 'protective_put' : 'collar')),
            FilledButton(onPressed: _run, child: const Text('Size hedge')),
          ]),
        ),
        const SizedBox(height: 16),
        if (_plan != null)
          FutureBody<Json>(
            future: _plan!,
            builder: (p) {
              if (p['available'] == false) return EmptyState(title: 'No plan', message: (p['reason'] ?? '').toString());
              return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                ResponsiveGrid(children: [
                  KpiCard(label: 'Contracts', value: '${p['contracts'] ?? '-'}', caption: 'exact ${fmtNum(asNum(p['exact_contracts']))} · lot ${p['lot_size']}'),
                  KpiCard(label: 'Strike', value: fmtNum(asNum(p['strike'] ?? p['put_strike']), dp: 0), caption: '${p['days_to_expiry'] ?? '-'} days'),
                  KpiCard(label: 'Premium', value: fmtInr(asNum(p['premium_total_inr'] ?? p['net_cost_inr'])), caption: '${fmtPct(asNum(p['premium_pct_of_portfolio'] ?? p['net_cost_pct_of_portfolio']), sign: false)} of portfolio'),
                  KpiCard(label: 'Coverage', value: fmtPct((asNum(p['coverage_ratio']) ?? 0) * 100, sign: false)),
                ]),
                const SizedBox(height: 16),
                Panel(title: 'Caveats', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [for (final c in asList(p['caveats'])) Padding(padding: const EdgeInsets.symmetric(vertical: 3), child: Text('• $c', style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.5)))])),
              ]);
            },
          ),
      ],
    );
  }
}

// ------------------------------------------------------------------ quant

class QuantPage extends StatefulWidget {
  const QuantPage({super.key});
  @override
  State<QuantPage> createState() => _QuantPageState();
}

class _QuantPageState extends State<QuantPage> {
  static const _methods = ['hrp', 'risk_parity', 'min_variance', 'max_sharpe'];
  int _tab = 0;
  String _method = 'hrp';
  Future<Json>? _res;

  @override
  void initState() {
    super.initState();
    portfolioStore.ensureLoaded();
  }

  Map<String, dynamic> get _pf => {'equity': portfolioStore.portfolio.equity, 'funds': portfolioStore.portfolio.funds, 'cash': portfolioStore.portfolio.cash};

  void _run() => setState(() {
        _res = switch (_tab) {
          0 => postJson('/api/quant/optimise', {'portfolio': _pf, 'method': _method, 'max_weight': 0.25, 'period': '2y', 'include_frontier': false}).then(asMap),
          1 => postJson('/api/quant/factors', {'portfolio': _pf, 'period': '2y', 'rolling': false}).then(asMap),
          _ => postJson('/api/quant/regime', {'portfolio': portfolioStore.portfolio.isEmpty ? null : _pf, 'period': '2y'}).then(asMap),
        };
      });

  @override
  Widget build(BuildContext context) {
    final needsHoldings = _tab != 2 && portfolioStore.portfolio.isEmpty;
    return PageScaffold(
      title: 'Risk Parity (HRP)',
      subtitle: 'Optimiser weights, factor exposures and market regime for your portfolio.',
      children: [
        SegTabs(labels: const ['Optimiser', 'Factors', 'Regime'], index: _tab, onChanged: (i) => setState(() { _tab = i; _res = null; })),
        const SizedBox(height: 14),
        Panel(
          child: Wrap(spacing: 14, runSpacing: 10, crossAxisAlignment: WrapCrossAlignment.center, children: [
            if (_tab == 0)
              SegTabs(labels: const ['HRP', 'Risk parity', 'Min variance', 'Max Sharpe'], index: _methods.indexOf(_method), onChanged: (i) => setState(() => _method = _methods[i])),
            FilledButton(onPressed: needsHoldings ? null : _run, child: const Text('Run')),
            if (needsHoldings) Text('Add holdings first.', style: AppText.sans(size: 13, color: Palette.inkSecondary)),
          ]),
        ),
        const SizedBox(height: 16),
        if (_res != null)
          FutureBody<Json>(
            future: _res!,
            builder: (r) {
              if (r['available'] == false) return EmptyState(title: 'Not available', message: (r['reason'] ?? '').toString());
              if (_tab == 0) {
                final w = asMap(r['weights']);
                final cur = asMap(r['current_weights']);
                final entries = w.entries.toList()..sort((a, b) => (asNum(b.value) ?? 0).compareTo(asNum(a.value) ?? 0));
                return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  ResponsiveGrid(children: [
                    KpiCard(label: 'Expected return', value: fmtPct(asNum(r['expected_return_pct']), sign: false)),
                    KpiCard(label: 'Volatility', value: fmtPct(asNum(r['volatility_pct']), sign: false)),
                    KpiCard(label: 'Sharpe', value: fmtNum(asNum(r['sharpe']))),
                    KpiCard(label: 'Effective holdings', value: fmtNum(asNum(r['effective_holdings']), dp: 1)),
                  ]),
                  const SizedBox(height: 16),
                  if ((r['why'] ?? '').toString().isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(r['why'].toString(), style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.5))),
                  Panel(
                    title: 'Target vs current weights',
                    padding: EdgeInsets.zero,
                    child: DataTableX(columns: const ['Holding', 'Target %', 'Current %', 'Drift'], rows: [
                      for (final e in entries)
                        [e.key, fmtNum((asNum(e.value) ?? 0) * 100, dp: 1), fmtNum((asNum(cur[e.key]) ?? 0) * 100, dp: 1), fmtNum(((asNum(e.value) ?? 0) - (asNum(cur[e.key]) ?? 0)) * 100, dp: 1)]
                    ]),
                  ),
                ]);
              }
              if (_tab == 1) {
                final betas = asMap(r['betas']);
                return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  ResponsiveGrid(columns: 3, children: [
                    KpiCard(label: 'Annual alpha', value: fmtPct(asNum(r['alpha_annual_pct']))),
                    KpiCard(label: 'R²', value: fmtNum(asNum(r['r_squared']))),
                    KpiCard(label: 'Observations', value: '${r['observations'] ?? '-'}'),
                  ]),
                  const SizedBox(height: 16),
                  Panel(
                    title: 'Factor betas',
                    padding: EdgeInsets.zero,
                    child: DataTableX(columns: const ['Factor', 'Beta', 't-stat', 'Contribution %'], rows: [
                      for (final e in betas.entries) [asMap(e.value)['label'] ?? e.key, fmtNum(asNum(asMap(e.value)['beta'])), fmtNum(asNum(asMap(e.value)['t_stat'])), fmtNum(asNum(asMap(e.value)['contribution_pct']))]
                    ]),
                  ),
                  if ((r['interpretation'] ?? '').toString().isNotEmpty) Padding(padding: const EdgeInsets.only(top: 12), child: Text(r['interpretation'].toString(), style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.5))),
                ]);
              }
              final m = asMap(r['metrics']);
              return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                ResponsiveGrid(children: [
                  KpiCard(label: 'Regime', value: (r['current_regime_label'] ?? r['current_regime'] ?? '-').toString(), caption: '${r['days_in_regime'] ?? '-'} days'),
                  KpiCard(label: 'Annualised vol', value: fmtPct(asNum(m['annualised_volatility_pct']), sign: false)),
                  KpiCard(label: '20d drawdown', value: fmtPct(asNum(m['drawdown_20d_pct']), sign: false)),
                  KpiCard(label: 'Avg correlation', value: fmtNum(asNum(m['average_correlation']))),
                ]),
                const SizedBox(height: 16),
                Panel(title: 'Guidance', child: Text((r['guidance'] ?? '').toString(), style: AppText.sans(size: 14, color: Palette.ink, height: 1.55))),
              ]);
            },
          ),
      ],
    );
  }
}

// -------------------------------------------------------------------- lab

class LabPage extends StatefulWidget {
  const LabPage({super.key});
  @override
  State<LabPage> createState() => _LabPageState();
}

class _LabPageState extends State<LabPage> {
  final _symbol = TextEditingController(text: 'RELIANCE');
  final _start = TextEditingController(text: '2022-01-01');
  final _end = TextEditingController(text: '2025-12-31');
  final _capital = TextEditingController(text: '1000000');
  String? _strategy;
  bool _walk = false;
  Future<Json>? _res;
  late final Future<Json> _strategies = getJson('/api/engine/strategies').then(asMap);

  static const _costs = {'brokerage_pct': 0.0003, 'brokerage_cap': 20.0, 'stt_pct': 0.001, 'slippage_pct': 0.0005};

  void _run(Json spec) {
    final base = {
      'symbol': _symbol.text.trim().toUpperCase(),
      'start': _start.text.trim(),
      'end': _end.text.trim(),
      'strategy': spec['name'],
      'initial_capital': double.tryParse(_capital.text) ?? 1000000,
      'sizer': {'name': 'percent', 'params': {'percent': 0.1}},
      'costs': _costs,
    };
    setState(() => _res = _walk
        ? postJson('/api/engine/walk-forward', {...base, 'folds': 4, 'in_sample_ratio': 0.7, 'objective': 'sharpe', 'ranges': spec['ranges']}).then(asMap)
        : postJson('/api/engine/run', {...base, 'params': spec['params'], 'permutation_test': true, 'permutations': 200}).then(asMap));
  }

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Strategy Lab',
      subtitle: 'Event-driven backtests with costs, a permutation significance test, and walk-forward validation.',
      children: [
        FutureBody<Json>(
          future: _strategies,
          builder: (s) {
            final list = asList(s['strategies']).map(asMap).toList();
            if (list.isEmpty) return const EmptyState(title: 'No strategies registered');
            _strategy ??= list.first['name'].toString();
            final spec = list.firstWhere((x) => x['name'] == _strategy, orElse: () => list.first);
            return Panel(
              child: Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.end, children: [
                _field(_symbol, 'Symbol', 150, number: false),
                _field(_start, 'Start', 130, number: false),
                _field(_end, 'End', 130, number: false),
                _field(_capital, 'Capital (₹)', 150),
                SizedBox(
                  width: 240,
                  child: DropdownButtonFormField<String>(
                    initialValue: _strategy,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Strategy'),
                    items: [for (final x in list) DropdownMenuItem(value: x['name'].toString(), child: Text((x['label'] ?? x['name']).toString(), overflow: TextOverflow.ellipsis))],
                    onChanged: (v) => setState(() => _strategy = v),
                  ),
                ),
                SegTabs(labels: const ['Single run', 'Walk-forward'], index: _walk ? 1 : 0, onChanged: (i) => setState(() => _walk = i == 1)),
                FilledButton(onPressed: () => _run(spec), child: const Text('Run')),
              ]),
            );
          },
        ),
        const SizedBox(height: 16),
        if (_res != null)
          FutureBody<Json>(
            future: _res!,
            builder: (r) => _walk ? _walkResult(r) : _runResult(r),
          ),
      ],
    );
  }

  Widget _runResult(Json r) {
    final perf = asMap(r['performance']);
    final bench = asMap(r['benchmark']);
    final tr = asMap(perf['trades']);
    final curve = asList(r['equity_curve']).map(asMap).toList();
    final pt = asMap(r['permutation_test']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      ResponsiveGrid(children: [
        KpiCard(label: 'Total return', value: fmtPct(asNum(perf['total_return_pct'])), caption: 'Buy & hold ${fmtPct(asNum(bench['total_return_pct']))}'),
        KpiCard(label: 'CAGR', value: fmtPct(asNum(perf['cagr_pct']))),
        KpiCard(label: 'Sharpe', value: fmtNum(asNum(perf['sharpe']))),
        KpiCard(label: 'Max drawdown', value: fmtPct(asNum(perf['max_drawdown_pct']), sign: false)),
      ]),
      const SizedBox(height: 16),
      Panel(
        title: 'Equity curve',
        child: LineChartX(
          height: 280,
          yFormat: (v) => fmtInr(v),
          xFormat: (x) { final i = x.round(); return i >= 0 && i < curve.length ? axisSlice(curve[i]['date'], 0, 7) : ''; },
          series: [Series('Strategy', [for (var i = 0; i < curve.length; i++) FlSpot(i.toDouble(), asNum(curve[i]['equity']) ?? 0)], Palette.primary, area: true)],
        ),
      ),
      const SizedBox(height: 16),
      ResponsiveGrid(columns: 2, children: [
        Panel(title: 'Trade statistics', child: Wrap(spacing: 28, runSpacing: 10, children: [
          _kv('Trades', '${tr['trade_count'] ?? 0}'),
          _kv('Win rate', fmtPct(asNum(tr['win_rate_pct']), sign: false)),
          _kv('Profit factor', fmtNum(asNum(tr['profit_factor']))),
          _kv('Alpha vs buy & hold', fmtPct(asNum(r['alpha_vs_buy_hold_pct']))),
        ])),
        Panel(title: 'Significance (permutation test)', child: Text(pt['available'] == true ? '${pt['verdict'] ?? ''}\n\np-value (return) ${fmtNum(asNum(pt['p_value_return']), dp: 3)} · ${pt['significant_at_5pct'] == true ? 'significant at 5%' : 'not significant at 5%'}\n${pt['caveat'] ?? ''}' : (pt['reason'] ?? 'Not run.').toString(), style: AppText.sans(size: 13, color: Palette.ink, height: 1.5))),
      ]),
    ]);
  }

  Widget _walkResult(Json r) {
    final folds = asList(r['folds']).map(asMap).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      ResponsiveGrid(children: [
        KpiCard(label: 'Mean in-sample', value: fmtPct(asNum(r['mean_in_sample_return_pct']))),
        KpiCard(label: 'Mean out-of-sample', value: fmtPct(asNum(r['mean_out_of_sample_return_pct']))),
        KpiCard(label: 'Efficiency', value: fmtNum(asNum(r['walk_forward_efficiency']))),
        KpiCard(label: 'Positive OOS folds', value: '${r['positive_oos_folds'] ?? 0} / ${r['completed_folds'] ?? 0}'),
      ]),
      const SizedBox(height: 16),
      Panel(title: 'Verdict', child: Text((r['verdict'] ?? '').toString(), style: AppText.sans(size: 14, color: Palette.ink, height: 1.55))),
      const SizedBox(height: 16),
      Panel(
        title: 'Folds',
        padding: EdgeInsets.zero,
        child: DataTableX(columns: const ['Fold', 'In-sample %', 'Out-of-sample %', 'Best params'], rows: [
          for (final f in folds)
            ['${f['fold'] ?? '-'}', f['skipped'] == true ? 'skipped' : fmtPct(asNum(f['in_sample_return_pct'])), f['skipped'] == true ? (f['reason'] ?? '').toString() : fmtPct(asNum(f['out_of_sample_return_pct'])), asMap(f['best_params']).entries.map((e) => '${e.key}=${e.value}').join(', ')]
        ]),
      ),
    ]);
  }
}

// ------------------------------------------------------------------ paper

class PaperPage extends StatefulWidget {
  const PaperPage({super.key});
  @override
  State<PaperPage> createState() => _PaperPageState();
}

class _PaperPageState extends State<PaperPage> {
  final _name = TextEditingController(text: 'My paper book');
  final _capital = TextEditingController(text: '1000000');
  late Future<Json> _accounts = _load();
  int? _selected;
  Future<Json> _load() => getJson('/api/paper', account: true).then(asMap);

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Paper Trading',
      subtitle: 'A persisted simulated ledger. Orders and signals are audited; nothing here places a real trade.',
      children: [
        Panel(
          title: 'New paper account',
          child: Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.end, children: [
            _field(_name, 'Name', 240, number: false),
            _field(_capital, 'Initial capital (₹)', 180),
            FilledButton(
              onPressed: () async {
                await postJson('/api/paper', {'name': _name.text.trim(), 'initial_capital': double.tryParse(_capital.text) ?? 1000000}, account: true);
                setState(() => _accounts = _load());
              },
              child: const Text('Create'),
            ),
          ]),
        ),
        const SizedBox(height: 16),
        FutureBody<Json>(
          future: _accounts,
          builder: (r) {
            final list = asList(r['accounts']).map(asMap).toList();
            if (list.isEmpty) return const EmptyState(title: 'No paper accounts yet', message: 'Create one above to start a simulated ledger.');
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Panel(
                title: 'Accounts',
                padding: EdgeInsets.zero,
                child: DataTableX(
                  columns: const ['Name', 'Capital', 'Cash', 'Active'],
                  onRowTap: (i) => setState(() => _selected = asNum(list[i]['id'])?.toInt()),
                  rows: [for (final a in list) [a['name'], fmtInr(asNum(a['initial_capital'])), fmtInr(asNum(a['cash'])), a['active'] == true ? 'yes' : 'no']],
                ),
              ),
              if (_selected != null) ...[const SizedBox(height: 16), _PaperDetail(key: ValueKey(_selected), id: _selected!)],
            ]);
          },
        ),
      ],
    );
  }
}

class _PaperDetail extends StatelessWidget {
  const _PaperDetail({super.key, required this.id});
  final int id;
  @override
  Widget build(BuildContext context) {
    return FutureBody<List<Json>>(
      future: Future.wait([getJson('/api/paper/$id', account: true).then(asMap), getJson('/api/paper/$id/orders', account: true).then(asMap), getJson('/api/paper/$id/signals', account: true).then(asMap)]),
      builder: (res) {
        final v = asMap(res[0]['valuation']);
        final div = asMap(res[0]['divergence']);
        final orders = asList(res[1]['orders']).map(asMap).toList();
        final signals = asList(res[2]['signals']).map(asMap).toList();
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          ResponsiveGrid(children: [
            KpiCard(label: 'Equity', value: fmtInr(asNum(v['equity'])), delta: asNum(v['total_return_pct'])),
            KpiCard(label: 'Realised P&L', value: fmtInr(asNum(v['realised_pnl_inr']))),
            KpiCard(label: 'Unrealised P&L', value: fmtInr(asNum(v['unrealised_pnl_inr']))),
            KpiCard(label: 'Fees paid', value: fmtInr(asNum(v['total_fees_inr']))),
          ]),
          if ((div['verdict'] ?? '').toString().isNotEmpty) ...[const SizedBox(height: 12), Text('${div['verdict']}', style: AppText.sans(size: 13, color: Palette.inkSecondary))],
          const SizedBox(height: 16),
          Panel(title: 'Open positions', padding: EdgeInsets.zero, child: DataTableX(columns: const ['Symbol', 'Qty', 'Avg cost', 'Price', 'Value', 'P&L %'], rows: [for (final p in asList(v['open_positions']).map(asMap)) [p['symbol'], fmtNum(asNum(p['quantity']), dp: 2), fmtNum(asNum(p['avg_cost'])), fmtNum(asNum(p['price'])), fmtInr(asNum(p['value'])), fmtPct(asNum(p['unrealised_pnl_pct']))]])),
          const SizedBox(height: 16),
          Panel(title: 'Orders', padding: EdgeInsets.zero, child: DataTableX(columns: const ['Symbol', 'Side', 'Qty', 'Price', 'Fees', 'Realised'], numericFrom: 2, rows: [for (final o in orders) [o['symbol'], StatusPill(o['side'].toString(), tone: o['side'] == 'BUY' ? Tone.buy : Tone.sell), fmtNum(asNum(o['quantity']), dp: 2), fmtNum(asNum(o['price'])), fmtNum(asNum(o['fees'])), fmtNum(asNum(o['realised_pnl']))]])),
          const SizedBox(height: 16),
          Panel(title: 'Signal audit', padding: EdgeInsets.zero, child: DataTableX(columns: const ['Symbol', 'Action', 'Score', 'Executed', 'Skip reason'], numericFrom: 2, rows: [for (final s in signals) [s['symbol'], s['action'], fmtNum(asNum(s['score']), dp: 0), s['executed'] == true ? 'yes' : 'no', s['skip_reason'] ?? '-']])),
        ]);
      },
    );
  }
}

// --------------------------------------------------------------- backtest

class BacktestPage extends StatefulWidget {
  const BacktestPage({super.key});
  @override
  State<BacktestPage> createState() => _BacktestPageState();
}

class _BacktestPageState extends State<BacktestPage> {
  final _ticker = TextEditingController(text: 'RELIANCE');
  final _start = TextEditingController(text: '2025-01-01');
  final _end = TextEditingController(text: '2025-12-31');
  final _capital = TextEditingController(text: '100000');
  String _strategy = 'RSI';
  Future<Json>? _res;

  void _run() => setState(() => _res = postJson('/api/backtest', {
        'ticker': _ticker.text.trim().toUpperCase(),
        'strategy': _strategy,
        'startDate': _start.text.trim(),
        'endDate': _end.text.trim(),
        'initialCapital': double.tryParse(_capital.text) ?? 100000,
        'fee': 0.001,
        'rsiOversold': 30,
        'rsiOverbought': 70,
        'smaFast': 20,
        'smaSlow': 50,
      }).then(asMap));

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Backtest',
      subtitle: 'A simple single-symbol strategy against buy-and-hold. Use the Strategy Lab for costs and significance testing.',
      children: [
        Panel(
          child: Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.end, children: [
            _field(_ticker, 'Ticker', 150, number: false),
            _field(_start, 'Start', 130, number: false),
            _field(_end, 'End', 130, number: false),
            _field(_capital, 'Capital (₹)', 150),
            SegTabs(labels: const ['RSI', 'SMA crossover'], index: _strategy == 'RSI' ? 0 : 1, onChanged: (i) => setState(() => _strategy = i == 0 ? 'RSI' : 'SMA')),
            FilledButton(onPressed: _run, child: const Text('Run backtest')),
          ]),
        ),
        const SizedBox(height: 16),
        if (_res != null)
          FutureBody<Json>(
            future: _res!,
            builder: (r) {
              final s = asMap(r['summary']);
              final curve = asList(r['equity_curve']).map(asMap).toList();
              final trades = asList(r['trades']).map(asMap).toList();
              return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                ResponsiveGrid(children: [
                  KpiCard(label: 'Strategy return', value: fmtPct(asNum(s['total_return_pct'])), caption: 'Buy & hold ${fmtPct(asNum(s['benchmark_return_pct']))}'),
                  KpiCard(label: 'CAGR', value: fmtPct(asNum(s['cagr_pct']))),
                  KpiCard(label: 'Sharpe', value: fmtNum(asNum(s['sharpe_ratio']))),
                  KpiCard(label: 'Max drawdown', value: fmtPct(asNum(s['max_drawdown_pct']), sign: false), caption: 'Win rate ${fmtPct(asNum(s['win_rate_pct']), sign: false)}'),
                ]),
                const SizedBox(height: 16),
                Panel(
                  title: 'Equity curve vs buy & hold',
                  child: LineChartX(
                    height: 280,
                    yFormat: (v) => fmtInr(v),
                    xFormat: (x) { final i = x.round(); return i >= 0 && i < curve.length ? chartDateLabel(curve[i]['date']) : ''; },
                    series: [
                      Series('Strategy', [for (var i = 0; i < curve.length; i++) FlSpot(i.toDouble(), asNum(curve[i]['strategy_value']) ?? 0)], Palette.primary, area: true),
                      Series('Buy & hold', [for (var i = 0; i < curve.length; i++) FlSpot(i.toDouble(), asNum(curve[i]['benchmark_value']) ?? 0)], Palette.inkMuted, dashed: true),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Panel(
                  title: '${trades.length} trades',
                  padding: EdgeInsets.zero,
                  child: DataTableX(columns: const ['Date', 'Type', 'Price', 'Shares', 'Fee', 'Portfolio value'], numericFrom: 2, rows: [for (final t in trades) [t['date'], StatusPill(t['type'].toString(), tone: t['type'] == 'BUY' ? Tone.buy : Tone.sell), fmtNum(asNum(t['price'])), fmtNum(asNum(t['shares']), dp: 2), fmtNum(asNum(t['fee'])), fmtInr(asNum(t['portfolio_value']))]]),
                ),
              ]);
            },
          ),
      ],
    );
  }
}
