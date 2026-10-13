import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../core/theme.dart';

class Series {
  const Series(this.label, this.points, this.color, {this.dashed = false, this.area = false, this.width = 2});
  final String label;
  final List<FlSpot> points;
  final Color color;
  final bool dashed;
  final bool area;
  final double width;
}

/// Shared line / area chart on fl_chart (one place for axes, grid, tooltips).
class LineChartX extends StatelessWidget {
  const LineChartX({
    super.key,
    required this.series,
    this.height = 260,
    this.xLabel,
    this.yFormat,
    this.xFormat,
  });
  final List<Series> series;
  final double height;
  final String Function(double)? yFormat;
  final String Function(double)? xFormat;
  final String? xLabel;

  @override
  Widget build(BuildContext context) {
    final nonEmpty = series.where((s) => s.points.isNotEmpty).toList();
    if (nonEmpty.isEmpty) return SizedBox(height: height, child: const Center(child: Text('No data')));
    final yf = yFormat ?? (v) => fmtNum(v, dp: 0);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(
        height: height,
        child: LineChart(LineChartData(
          minY: null,
          gridData: FlGridData(
            drawVerticalLine: false,
            getDrawingHorizontalLine: (_) => const FlLine(color: Palette.border, strokeWidth: 1),
          ),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 64,
                getTitlesWidget: (v, meta) => Text(yf(v), style: AppText.mono(size: 10, color: Palette.inkMuted)),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 24,
                getTitlesWidget: (v, meta) => Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text((xFormat ?? (x) => x.toStringAsFixed(0))(v),
                      style: AppText.mono(size: 10, color: Palette.inkMuted)),
                ),
              ),
            ),
          ),
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipItems: (spots) => [
                for (final s in spots)
                  LineTooltipItem('${nonEmpty[s.barIndex].label}  ${yf(s.y)}',
                      AppText.mono(size: 11, color: Colors.white)),
              ],
            ),
          ),
          lineBarsData: [
            for (final s in nonEmpty)
              LineChartBarData(
                spots: s.points,
                isCurved: true,
                curveSmoothness: 0.15,
                color: s.color,
                barWidth: s.width,
                dotData: const FlDotData(show: false),
                dashArray: s.dashed ? [5, 4] : null,
                belowBarData: BarAreaData(show: s.area, color: s.color.withValues(alpha: 0.08)),
              ),
          ],
        )),
      ),
      const SizedBox(height: 10),
      Wrap(spacing: 16, runSpacing: 6, children: [
        for (final s in nonEmpty)
          Row(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 12, height: 3, color: s.color),
            const SizedBox(width: 6),
            Text(s.label, style: AppText.sans(size: 12, color: Palette.inkSecondary)),
          ]),
      ]),
    ]);
  }
}

/// Horizontal weight bars (allocation by sector / cap / asset class).
class WeightBars extends StatelessWidget {
  const WeightBars({super.key, required this.slices});
  final List<(String label, double pct)> slices;
  @override
  Widget build(BuildContext context) {
    if (slices.isEmpty) return const SizedBox.shrink();
    return Column(children: [
      for (final (label, pct) in slices)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 5),
          child: Row(children: [
            SizedBox(width: 130, child: Text(label, overflow: TextOverflow.ellipsis, style: AppText.sans(size: 13))),
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(3),
                child: LinearProgressIndicator(
                  value: (pct / 100).clamp(0, 1),
                  minHeight: 8,
                  backgroundColor: Palette.subtle,
                  color: Palette.primary,
                ),
              ),
            ),
            SizedBox(width: 56, child: Text('${pct.toStringAsFixed(1)}%', textAlign: TextAlign.right, style: AppText.mono(size: 12))),
          ]),
        ),
    ]);
  }
}
