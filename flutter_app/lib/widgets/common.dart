import 'package:flutter/material.dart';

import '../core/theme.dart';

const double kMaxWidth = 1200;

bool isNarrow(BuildContext context) => MediaQuery.sizeOf(context).width < 760;

/// Centered content column used by every page.
class PageBox extends StatelessWidget {
  const PageBox({super.key, required this.child, this.padding});
  final Widget child;
  final EdgeInsets? padding;
  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: kMaxWidth),
        child: Padding(
          padding: padding ?? EdgeInsets.symmetric(horizontal: isNarrow(context) ? 16 : 28, vertical: 28),
          child: child,
        ),
      ),
    );
  }
}

/// Standard scrollable page: header + children.
class PageScaffold extends StatelessWidget {
  const PageScaffold({super.key, required this.title, this.subtitle, this.actions = const [], required this.children});
  final String title;
  final String? subtitle;
  final List<Widget> actions;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) {
    return PageBox(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        PageHeader(title: title, subtitle: subtitle, actions: actions),
        ...children,
      ]),
    );
  }
}

class PageHeader extends StatelessWidget {
  const PageHeader({super.key, required this.title, this.subtitle, this.actions = const []});
  final String title;
  final String? subtitle;
  final List<Widget> actions;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Wrap(
        alignment: WrapAlignment.spaceBetween,
        crossAxisAlignment: WrapCrossAlignment.end,
        runSpacing: 12,
        children: [
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: AppText.sans(size: 26, weight: FontWeight.w700, spacing: -0.4)),
              if (subtitle != null) ...[
                const SizedBox(height: 6),
                Text(subtitle!, style: AppText.sans(size: 14, color: Palette.inkSecondary, height: 1.45)),
              ],
            ]),
          ),
          if (actions.isNotEmpty) Wrap(spacing: 8, children: actions),
        ],
      ),
    );
  }
}

class Panel extends StatelessWidget {
  const Panel({super.key, required this.child, this.title, this.trailing, this.padding = const EdgeInsets.all(18)});
  final Widget child;
  final String? title;
  final Widget? trailing;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: Palette.card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Palette.border),
        boxShadow: const [BoxShadow(color: Color(0x0D0F172A), blurRadius: 2, offset: Offset(0, 1))],
      ),
      padding: padding,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (title != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Row(children: [
              Expanded(child: Text(title!, style: AppText.sans(size: 16, weight: FontWeight.w600))),
              ?trailing,
            ]),
          ),
        child,
      ]),
    );
  }
}

class KpiCard extends StatelessWidget {
  const KpiCard({super.key, required this.label, required this.value, this.delta, this.caption});
  final String label;
  final String value;
  final double? delta;
  final String? caption;
  @override
  Widget build(BuildContext context) {
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label.toUpperCase(), style: AppText.label()),
        const SizedBox(height: 8),
        Text(value, style: AppText.mono(size: 22, weight: FontWeight.w600)),
        if (delta != null) ...[const SizedBox(height: 6), DeltaBadge(delta!)],
        if (caption != null) ...[
          const SizedBox(height: 6),
          Text(caption!, style: AppText.sans(size: 12, color: Palette.inkSecondary)),
        ],
      ]),
    );
  }
}

class DeltaBadge extends StatelessWidget {
  const DeltaBadge(this.value, {super.key});
  final double value;
  @override
  Widget build(BuildContext context) {
    final c = deltaColor(value);
    final bg = value > 0 ? Palette.buySurface : (value < 0 ? Palette.sellSurface : Palette.subtle);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(99)),
      child: Text('${value > 0 ? '▲ ' : value < 0 ? '▼ ' : ''}${fmtPct(value, sign: false)}',
          style: AppText.mono(size: 12, color: c)),
    );
  }
}

enum Tone { buy, sell, hold, neutral, primary }

class StatusPill extends StatelessWidget {
  const StatusPill(this.text, {super.key, this.tone = Tone.neutral});
  final String text;
  final Tone tone;
  @override
  Widget build(BuildContext context) {
    final (fg, bg) = switch (tone) {
      Tone.buy => (Palette.buy, Palette.buySurface),
      Tone.sell => (Palette.sell, Palette.sellSurface),
      Tone.hold => (Palette.hold, Palette.holdSurface),
      Tone.primary => (Palette.primary, Palette.primarySubtle),
      Tone.neutral => (Palette.inkSecondary, Palette.subtle),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: fg.withValues(alpha: 0.25)),
      ),
      child: Text(text, style: AppText.sans(size: 12, weight: FontWeight.w600, color: fg)),
    );
  }
}

/// Honest empty state; used where no data source is connected (never mock data).
class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.title, this.message, this.icon = Icons.inbox_outlined, this.action});
  final String title;
  final String? message;
  final IconData icon;
  final Widget? action;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 32, color: Palette.inkMuted),
            const SizedBox(height: 12),
            Text(title, textAlign: TextAlign.center, style: AppText.sans(size: 16, weight: FontWeight.w600)),
            if (message != null) ...[
              const SizedBox(height: 6),
              Text(message!,
                  textAlign: TextAlign.center,
                  style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.45)),
            ],
            if (action != null) ...[const SizedBox(height: 16), action!],
          ]),
        ),
      ),
    );
  }
}

class ErrorState extends StatelessWidget {
  const ErrorState(this.error, {super.key, this.onRetry});
  final Object error;
  final VoidCallback? onRetry;
  @override
  Widget build(BuildContext context) => EmptyState(
        icon: Icons.error_outline,
        title: 'Could not load this data',
        message: error.toString().replaceFirst('Exception: ', ''),
        action: onRetry == null ? null : OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
      );
}

class Loading extends StatelessWidget {
  const Loading({super.key});
  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.all(48),
        child: Center(child: SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2.5))),
      );
}

/// Responsive grid: `columns` on wide screens, collapsing to 2 then 1.
class ResponsiveGrid extends StatelessWidget {
  const ResponsiveGrid({super.key, required this.children, this.columns = 4, this.gap = 16});
  final List<Widget> children;
  final int columns;
  final double gap;
  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      final cols = c.maxWidth < 560 ? 1 : (c.maxWidth < 900 ? (columns > 2 ? 2 : columns) : columns);
      final w = (c.maxWidth - gap * (cols - 1)) / cols;
      return Wrap(
        spacing: gap,
        runSpacing: gap,
        children: [for (final ch in children) SizedBox(width: w, child: ch)],
      );
    });
  }
}

/// Table: hairline rows, right-aligned mono numerics from [numericFrom].
class DataTableX extends StatelessWidget {
  const DataTableX({super.key, required this.columns, required this.rows, this.numericFrom = 1, this.onRowTap});
  final List<String> columns;
  final List<List<Object?>> rows;
  final int numericFrom;
  final void Function(int index)? onRowTap;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) return const EmptyState(title: 'No rows to show');
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: IntrinsicWidth(
        child: Column(children: [
          Container(
            color: Palette.canvas,
            padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
            child: Row(children: [
              for (var i = 0; i < columns.length; i++)
                _cell(
                    Text(columns[i].toUpperCase(),
                        style: AppText.label(), textAlign: i >= numericFrom ? TextAlign.right : TextAlign.left),
                    i),
            ]),
          ),
          const Divider(),
          for (var r = 0; r < rows.length; r++)
            InkWell(
              onTap: onRowTap == null ? null : () => onRowTap!(r),
              child: Container(
                decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: Palette.border))),
                padding: const EdgeInsets.symmetric(vertical: 11, horizontal: 12),
                child: Row(children: [
                  for (var i = 0; i < columns.length; i++) _cell(_value(rows[r], i), i),
                ]),
              ),
            ),
        ]),
      ),
    );
  }

  Widget _value(List<Object?> row, int i) {
    final v = i < row.length ? row[i] : null;
    if (v is Widget) return Align(alignment: i >= numericFrom ? Alignment.centerRight : Alignment.centerLeft, child: v);
    return Text('${v ?? '-'}',
        textAlign: i >= numericFrom ? TextAlign.right : TextAlign.left,
        style: i >= numericFrom ? AppText.mono(size: 13) : AppText.sans(size: 13, weight: FontWeight.w500));
  }

  Widget _cell(Widget w, int i) =>
      SizedBox(width: i == 0 ? 220 : 120, child: Padding(padding: const EdgeInsets.only(right: 12), child: w));
}

class SegTabs extends StatelessWidget {
  const SegTabs({super.key, required this.labels, required this.index, required this.onChanged});
  final List<String> labels;
  final int index;
  final ValueChanged<int> onChanged;
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Container(
        padding: const EdgeInsets.all(3),
        decoration: BoxDecoration(color: Palette.subtle, borderRadius: BorderRadius.circular(8)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          for (var i = 0; i < labels.length; i++)
            GestureDetector(
              onTap: () => onChanged(i),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  color: i == index ? Colors.white : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                  boxShadow: i == index ? const [BoxShadow(color: Color(0x14000000), blurRadius: 2)] : null,
                ),
                child: Text(labels[i],
                    style: AppText.sans(
                        size: 13, weight: FontWeight.w600, color: i == index ? Palette.primary : Palette.inkSecondary)),
              ),
            ),
        ]),
      ),
    );
  }
}

/// Renders a Riverpod [AsyncValue]-like future result with loading / error / data.
class FutureBody<T> extends StatelessWidget {
  const FutureBody({super.key, required this.future, required this.builder});
  final Future<T> future;
  final Widget Function(T data) builder;
  @override
  Widget build(BuildContext context) {
    return FutureBuilder<T>(
      future: future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const Loading();
        if (snap.hasError) return ErrorState(snap.error!);
        return builder(snap.data as T);
      },
    );
  }
}
