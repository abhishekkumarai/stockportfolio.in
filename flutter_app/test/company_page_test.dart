import 'package:flutter_test/flutter_test.dart';
import 'package:stockportfolio/features/research/company_page.dart';

List<(DateTime, double)> daily(int days, double Function(int) price) =>
    [for (var i = 0; i <= days; i++) (DateTime(2025, 1, 1).add(Duration(days: i)), price(i))];

void main() {
  test('returnOver measures from the bar at or before the target date', () {
    final s = daily(400, (i) => 100 + i.toDouble()); // +1 per day
    // last = 500 (day 400); 30 days back = day 370 = 470 -> +6.38%
    expect(returnOver(s, 30), closeTo((500 / 470 - 1) * 100, 1e-9));
    expect(returnOver(s, 365), closeTo((500 / 135 - 1) * 100, 1e-9));
  });

  test('returnOver is null when history does not reach back far enough', () {
    final s = daily(100, (i) => 100 + i.toDouble());
    expect(returnOver(s, 365), isNull); // never extrapolated or faked from the first bar
    expect(returnOver(s, 30), isNotNull);
  });

  test('returnOver handles empty, single-point and zero-base series', () {
    expect(returnOver([], 30), isNull);
    expect(returnOver([(DateTime(2025, 1, 1), 10)], 30), isNull);
    expect(returnOver(daily(60, (i) => i == 0 ? 0 : 5), 60), isNull);
  });

  test('parseSeries skips rows with a bad date or missing close', () {
    final s = parseSeries({
      'data': [
        {'date': '2025-01-01T00:00:00', 'close': 10},
        {'date': 'garbage', 'close': 11},
        {'date': '2025-01-03T00:00:00'},
        {'date': '2025-01-04T00:00:00', 'close': 12.5},
      ]
    });
    expect(s.length, 2);
    expect(s.last.$2, 12.5);
  });
}
