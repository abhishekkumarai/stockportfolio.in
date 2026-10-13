import 'package:flutter_test/flutter_test.dart';
import 'package:stockportfolio/core/api/http_client.dart';
import 'package:stockportfolio/core/theme.dart';

void main() {
  test('fmtNum uses Indian digit grouping', () {
    expect(fmtNum(1234567.891), '12,34,567.89');
    expect(fmtNum(999, dp: 0), '999');
    expect(fmtNum(100000, dp: 0), '1,00,000');
    expect(fmtNum(-1500.5), '-1,500.50');
    expect(fmtNum(null), '-');
  });

  test('fmtPct signs positives only', () {
    expect(fmtPct(1.234), '+1.23%');
    expect(fmtPct(-0.5), '-0.50%');
    expect(fmtPct(2, sign: false), '2.00%');
  });

  test('queryString drops empties and repeats lists', () {
    expect(queryString({'a': 1, 'b': '', 'c': null, 'd': ['x', 'y']}), '?a=1&d=x&d=y');
    expect(queryString({}), '');
  });
}
