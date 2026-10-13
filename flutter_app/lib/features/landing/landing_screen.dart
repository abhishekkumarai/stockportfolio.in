import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/http_client.dart';
import '../../core/theme.dart';
import '../../widgets/common.dart';

/// Public landing page. Left-aligned hero with a live market panel (real
/// backend data only), then feature rows that alternate text and detail.
class LandingScreen extends StatelessWidget {
  const LandingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final narrow = isNarrow(context);
    return Column(children: [
      PageBox(
        padding: EdgeInsets.fromLTRB(narrow ? 16 : 28, 56, narrow ? 16 : 28, 40),
        child: narrow
            ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [_heroText(context), const SizedBox(height: 32), const _LivePanel()])
            : Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                Expanded(flex: 6, child: _heroText(context)),
                const SizedBox(width: 48),
                const Expanded(flex: 5, child: _LivePanel()),
              ]),
      ),
      const _Divider(),
      PageBox(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('THE OLD WAY', style: AppText.label()),
          const SizedBox(height: 10),
          Text('Researching one stock still takes ten tabs.',
              style: AppText.sans(size: 30, weight: FontWeight.w700, spacing: -0.5, height: 1.2)),
          const SizedBox(height: 28),
          const _FeatureRow(
            tag: 'DISCOVER',
            title: 'Find candidates ranked by evidence',
            body:
                'The NSE universe is scored on technicals and fundamentals. Every buy, sell or hold call lists the numbers that produced it.',
            path: '/recommendations',
            cta: 'See ranked calls',
          ),
          const _FeatureRow(
            tag: 'UNDERSTAND',
            title: 'Look inside a company in one screen',
            body: 'Piotroski score, trend, sentiment and price history for any listed company, searchable with Ctrl+K.',
            path: '/analyse',
            cta: 'Open equity deep dive',
          ),
          const _FeatureRow(
            tag: 'PROTECT',
            title: 'Know what your portfolio can lose',
            body:
                'Wealth cone, value at risk and a crash simulator that replays past crises on your actual holdings, with tax-aware rebalancing.',
            path: '/portfolio',
            cta: 'Stress your portfolio',
          ),
          const _FeatureRow(
            tag: 'HEDGE',
            title: 'Size protection before you need it',
            body: 'Options chain with put-call ratio, max pain and open-interest walls, plus index put and collar sizing.',
            path: '/options',
            cta: 'Open options chain',
          ),
        ]),
      ),
      const _Divider(),
      PageBox(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('TOOLKIT', style: AppText.label()),
          const SizedBox(height: 10),
          Text('Everything else an Indian investor reaches for.',
              style: AppText.sans(size: 26, weight: FontWeight.w700, spacing: -0.4)),
          const SizedBox(height: 22),
          Wrap(spacing: 10, runSpacing: 10, children: [
            for (final (label, path) in const [
              ('Screener', '/screener'),
              ('Market Today', '/market'),
              ('Mutual Funds', '/mutualfunds'),
              ('Macro Radar', '/macro'),
              ('Paper Trading', '/paper'),
              ('Backtest', '/backtest'),
              ('SIP & tax calculators', '/calculators'),
              ('Alerts', '/alerts'),
            ])
              ActionChip(
                label: Text(label, style: AppText.sans(size: 13, weight: FontWeight.w600)),
                backgroundColor: Colors.white,
                side: const BorderSide(color: Palette.borderStrong),
                onPressed: () => context.go(path),
              ),
          ]),
          const SizedBox(height: 40),
          FilledButton(onPressed: () => context.go('/auth'), child: const Text('Create a free account')),
        ]),
      ),
    ]);
  }

  Widget _heroText(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Know what to buy, sell or hold. And why.',
            style: AppText.sans(size: isNarrow(context) ? 34 : 48, weight: FontWeight.w700, spacing: -1, height: 1.08)),
        const SizedBox(height: 18),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Text(
            'Ranked, explained recommendations for Indian stocks, with portfolio risk, tax-aware exits and derivatives '
            'analytics in one place. The numbers are inputs; the verdict is the product.',
            style: AppText.sans(size: 16, color: Palette.inkSecondary, height: 1.55),
          ),
        ),
        const SizedBox(height: 28),
        Wrap(spacing: 12, runSpacing: 12, children: [
          FilledButton(onPressed: () => context.go('/auth'), child: const Text('Create free account')),
          OutlinedButton(onPressed: () => context.go('/recommendations'), child: const Text('See ranked calls')),
        ]),
      ]);
}

class _Divider extends StatelessWidget {
  const _Divider();
  @override
  Widget build(BuildContext context) => const Divider(height: 1);
}

class _FeatureRow extends StatelessWidget {
  const _FeatureRow({required this.tag, required this.title, required this.body, required this.path, required this.cta});
  final String tag, title, body, path, cta;
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(border: Border(top: BorderSide(color: Palette.border))),
      padding: const EdgeInsets.symmetric(vertical: 26),
      child: Wrap(spacing: 40, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.start, children: [
        SizedBox(width: 120, child: Text(tag, style: AppText.label(color: Palette.primary))),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: AppText.sans(size: 20, weight: FontWeight.w600, spacing: -0.2)),
            const SizedBox(height: 8),
            Text(body, style: AppText.sans(size: 14, color: Palette.inkSecondary, height: 1.55)),
            const SizedBox(height: 10),
            InkWell(
              onTap: () => context.go(path),
              child: Text('$cta →', style: AppText.sans(size: 14, weight: FontWeight.w600, color: Palette.primary)),
            ),
          ]),
        ),
      ]),
    );
  }
}

/// Live index panel from /api/macro. No mock data: errors and unavailable
/// states are shown as such.
class _LivePanel extends StatelessWidget {
  const _LivePanel();
  @override
  Widget build(BuildContext context) {
    return Panel(
      title: 'Market now',
      trailing: const StatusPill('Live data', tone: Tone.primary),
      child: FutureBuilder(
        future: getJson('/api/macro'),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const Loading();
          if (snap.hasError) return ErrorState(snap.error!);
          final d = asMap(snap.data);
          if (d['available'] == false) {
            return EmptyState(title: 'Market data unavailable', message: (d['reason'] ?? 'Try again shortly.').toString());
          }
          final idx = asMap(d['indices']);
          final rows = <(String, Json)>[
            ('NIFTY 50', asMap(idx['nifty50'])),
            ('SENSEX', asMap(idx['sensex'])),
          ];
          final vix = asMap(d['vix']);
          final regime = asMap(d['regime']);
          return Column(children: [
            for (final (name, m) in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Row(children: [
                  Expanded(child: Text(name, style: AppText.sans(size: 14, weight: FontWeight.w600))),
                  Text(fmtNum(asNum(m['current'])), style: AppText.mono(size: 15)),
                  const SizedBox(width: 12),
                  if (asNum(m['change_pct']) != null) DeltaBadge(asNum(m['change_pct'])!),
                ]),
              ),
            const Divider(),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Row(children: [
                Expanded(child: Text('INDIA VIX', style: AppText.sans(size: 14, weight: FontWeight.w600))),
                Text(fmtNum(asNum(vix['current'])), style: AppText.mono(size: 15)),
              ]),
            ),
            if (regime['title'] != null) ...[
              const Divider(),
              const SizedBox(height: 10),
              Align(
                alignment: Alignment.centerLeft,
                child: Text('Regime: ${regime['title']} · ${regime['posture'] ?? ''}',
                    style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.4)),
              ),
            ],
          ]);
        },
      ),
    );
  }
}
