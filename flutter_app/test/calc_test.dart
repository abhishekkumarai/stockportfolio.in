import 'package:flutter_test/flutter_test.dart';
import 'package:stockportfolio/features/tools/calc.dart' as c;

void main() {
  test('SIP: 10k/month, 12%, 10y matches annuity-due formula', () {
    final r = c.sip(10000, 12, 10);
    expect(r.invested, 1200000);
    expect(r.futureValue, closeTo(2323391, 2000)); // ~23.2 lakh
  });

  test('Lumpsum: 1L at 10% for 2y = 1.21L', () {
    expect(c.lumpsum(100000, 10, 2).futureValue, closeTo(121000, 0.01));
  });

  test('SWP: zero-return corpus lasts corpus/withdrawal months', () {
    final r = c.swp(120000, 10000, 0, 2);
    expect(r.exhaustedMonth, 12);
    expect(r.withdrawn, closeTo(120000, 0.01));
  });

  test('SWP: sustainable withdrawal leaves a balance', () {
    expect(c.swp(1000000, 1000, 8, 5).exhaustedMonth, isNull);
  });

  test('PPF: 1.5L/yr at 7.1% for 15y is about 40.7 lakh', () {
    expect(c.ppf(150000, 7.1, 15).maturity, closeTo(4068209, 5000));
  });

  test('FD: 1L at 8% quarterly for 1y', () {
    expect(c.fd(100000, 8, 1).maturity, closeTo(108243.2, 0.5));
  });

  test('CAGR: doubling in 5y is ~14.87%', () {
    expect(c.cagr(100, 200, 5), closeTo(14.87, 0.01));
    expect(c.cagr(0, 200, 5).isNaN, isTrue);
  });

  test('HRA exemption takes the least of three', () {
    // basic 50k/m = 600k/yr; HRA 240k; rent 300k; metro: min(240k, 300k-60k=240k, 300k)
    expect(c.hraExemption(basicPlusDa: 600000, hraReceived: 240000, rentPaid: 300000, metro: true), 240000);
    // non-metro caps at 40% = 240k as well; lower rent binds
    expect(c.hraExemption(basicPlusDa: 600000, hraReceived: 240000, rentPaid: 120000, metro: false), 60000);
  });

  test('GST inclusive and exclusive', () {
    final ex = c.gst(1000, 18, amountIncludesGst: false);
    expect(ex.gst, 180);
    expect(ex.total, 1180);
    final inc = c.gst(1180, 18, amountIncludesGst: true);
    expect(inc.base, closeTo(1000, 0.001));
  });

  test('EPF corpus grows and splits contributions', () {
    final r = c.epf(monthlyBasic: 50000, currentAge: 30, retireAge: 31, annualRatePct: 0);
    expect(r.employeeTotal, closeTo(72000, 0.01)); // 12% * 50k * 12
    expect(r.employerTotal, closeTo(22020, 0.01)); // 3.67% * 50k * 12
    expect(r.corpus, closeTo(94020, 0.01));
  });

  test('Retirement: needs a positive SIP and corpus', () {
    final r = c.retirement(
        currentMonthlyExpense: 50000, currentAge: 30, retireAge: 60, lifeExpectancy: 85, inflationPct: 6, preReturnPct: 12, postReturnPct: 8);
    expect(r.corpusNeeded, greaterThan(0));
    expect(r.monthlySip, greaterThan(0));
    expect(r.monthlyExpenseAtRetirement, closeTo(50000 * 5.7435, 50));
  });

  group('Income tax FY25-26 (excl. surcharge)', () {
    test('new regime: 12.75L gross is nil after std deduction + rebate', () {
      expect(c.incomeTax(1275000, newRegime: true).total, 0);
    });
    test('new regime: 15L gross', () {
      // taxable 14.25L: 4-8L 5% = 20k, 8-12L 10% = 40k, 12-14.25L 15% = 33,750 => 93,750 (+4% cess)
      final r = c.incomeTax(1500000, newRegime: true);
      expect(r.tax, closeTo(93750, 0.01));
      expect(r.total, closeTo(97500, 0.01));
    });
    test('old regime: 10L gross, no deductions', () {
      // taxable 9.5L: 2.5-5L 5% = 12.5k, 5-9.5L 20% = 90k => 102.5k
      expect(c.incomeTax(1000000, newRegime: false).tax, closeTo(102500, 0.01));
    });
    test('old regime rebate up to 5L taxable', () {
      expect(c.incomeTax(550000, newRegime: false).total, 0);
    });
  });
}
