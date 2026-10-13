import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/http_client.dart';
import '../../core/theme.dart';
import '../../widgets/common.dart';
import 'portfolio_pages.dart';
import 'portfolio_store.dart';

/// Master Console: the signed-in home. KPI row from the real valuation, then
/// tabbed analytics and a searchable holdings table.
class ConsolePage extends StatefulWidget {
  const ConsolePage({super.key});
  @override
  State<ConsolePage> createState() => _ConsolePageState();
}

class _ConsolePageState extends State<ConsolePage> {
  int _tab = 0;
  String _q = '';

  @override
  void initState() {
    super.initState();
    portfolioStore.ensureLoaded();
  }

  @override
  Widget build(BuildContext context) {
    return PortfolioGate(
      title: 'Master Console',
      subtitle: 'Your portfolio, its risk and what to do next.',
      actions: [
        OutlinedButton(onPressed: () => context.go('/portfolio/holdings'), child: const Text('Manage holdings')),
        FilledButton(onPressed: () => context.go('/recommendations'), child: const Text('Ranked calls')),
      ],
      builder: (context, s) {
        final totals = asMap(s.valuation?['totals']);
        final danger = asMap(s.danger);
        final growth = asMap(s.growth);
        final rows = asList(s.valuation?['holdings']).map(asMap).where((r) {
          if (_q.isEmpty) return true;
          return '${r['name']} ${r['key']} ${r['sector']}'.toLowerCase().contains(_q.toLowerCase());
        }).toList();
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          ResponsiveGrid(children: [
            KpiCard(
              label: 'Net asset value',
              value: fmtInr(asNum(totals['current_value'])),
              delta: asNum(totals['pnl_pct']),
              caption: 'Invested ${fmtInr(asNum(totals['invested']))}',
            ),
            KpiCard(label: 'Unrealised P&L', value: fmtInr(asNum(totals['pnl']))),
            KpiCard(
                label: 'Risk',
                value: '${danger['danger_score'] ?? '-'}',
                caption: '${danger['danger_level'] ?? ''} · resilience ${danger['resilience_score'] ?? '-'}'),
            KpiCard(
                label: 'Growth',
                value: '${growth['growth_score'] ?? '-'}',
                caption: '${growth['growth_level'] ?? ''} · CAGR ${fmtPct(asNum(asMap(growth['pillars'])['projected_cagr_pct']), sign: false)}'),
          ]),
          const SizedBox(height: 24),
          SegTabs(labels: const ['Wealth & risk', 'Holdings'], index: _tab, onChanged: (i) => setState(() => _tab = i)),
          const SizedBox(height: 16),
          if (_tab == 0)
            PortfolioOverviewBody(store: s)
          else
            Panel(
              title: 'Holdings',
              trailing: SizedBox(
                width: 220,
                child: TextField(
                  onChanged: (v) => setState(() => _q = v),
                  decoration: const InputDecoration(hintText: 'Filter', prefixIcon: Icon(Icons.search, size: 18)),
                ),
              ),
              padding: const EdgeInsets.all(0),
              child: DataTableX(
                columns: const ['Holding', 'Sector', 'Value', 'P&L %', 'Weight'],
                numericFrom: 2,
                onRowTap: (i) {
                  final key = rows[i]['key'].toString();
                  if (rows[i]['kind'] == 'equity') context.go('/analyse/${Uri.encodeComponent(key)}');
                },
                rows: [
                  for (final r in rows)
                    [
                      r['name'] ?? r['key'],
                      r['sector'] ?? '-',
                      fmtInr(asNum(r['current_value'])),
                      Text(fmtPct(asNum(r['pnl_pct'])), style: AppText.mono(color: deltaColor(asNum(r['pnl_pct'])))),
                      fmtPct(asNum(r['weight_pct']), sign: false),
                    ]
                ],
              ),
            ),
        ]);
      },
    );
  }
}
