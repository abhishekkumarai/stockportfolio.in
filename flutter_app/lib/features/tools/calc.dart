import 'dart:math' as math;

/// Pure calculator maths (no UI), unit tested in test/calc_test.dart.

/// Future value of a monthly SIP with end-of-period... SIP paid at the start
/// of each month (annuity due), monthly compounding at [annualRatePct]/12.
({double invested, double futureValue, double gain}) sip(double monthly, double annualRatePct, double years) {
  final n = (years * 12).round();
  final r = annualRatePct / 100 / 12;
  final invested = monthly * n;
  final fv = r == 0 ? invested : monthly * ((math.pow(1 + r, n) - 1) / r) * (1 + r);
  return (invested: invested, futureValue: fv, gain: fv - invested);
}

({double invested, double futureValue, double gain}) lumpsum(double amount, double annualRatePct, double years) {
  final fv = amount * math.pow(1 + annualRatePct / 100, years);
  return (invested: amount, futureValue: fv, gain: fv - amount);
}

/// Systematic withdrawal: month-by-month simulation. Returns the corpus left
/// after [years] and the month the corpus ran out (null if it lasts).
({double remaining, int? exhaustedMonth, double withdrawn}) swp(
    double corpus, double monthlyWithdrawal, double annualRatePct, double years) {
  final r = annualRatePct / 100 / 12;
  var bal = corpus;
  var withdrawn = 0.0;
  final n = (years * 12).round();
  for (var m = 1; m <= n; m++) {
    bal += bal * r;
    final take = math.min(monthlyWithdrawal, bal);
    bal -= take;
    withdrawn += take;
    if (bal <= 0.005) return (remaining: 0, exhaustedMonth: m, withdrawn: withdrawn);
  }
  return (remaining: bal, exhaustedMonth: null, withdrawn: withdrawn);
}

/// PPF: yearly deposit at the start of each year, annual compounding.
({double invested, double maturity, double interest}) ppf(double yearly, double annualRatePct, int years) {
  var bal = 0.0;
  for (var y = 0; y < years; y++) {
    bal = (bal + yearly) * (1 + annualRatePct / 100);
  }
  final invested = yearly * years;
  return (invested: invested, maturity: bal, interest: bal - invested);
}

/// Fixed deposit with [compoundingsPerYear] compounding periods.
({double maturity, double interest}) fd(double principal, double annualRatePct, double years, {int compoundingsPerYear = 4}) {
  final m = principal * math.pow(1 + annualRatePct / 100 / compoundingsPerYear, compoundingsPerYear * years);
  return (maturity: m, interest: m - principal);
}

/// CAGR as a percentage.
double cagr(double begin, double end, double years) {
  if (begin <= 0 || years <= 0) return double.nan;
  return (math.pow(end / begin, 1 / years) - 1) * 100;
}

/// HRA exemption (annual): least of actual HRA, rent paid minus 10% of salary,
/// and 50% (metro) / 40% (non-metro) of salary. Salary = basic + DA.
double hraExemption({required double basicPlusDa, required double hraReceived, required double rentPaid, required bool metro}) {
  final a = hraReceived;
  final b = math.max(0.0, rentPaid - 0.10 * basicPlusDa);
  final c = (metro ? 0.5 : 0.4) * basicPlusDa;
  return math.min(a, math.min(b, c));
}

/// Retirement corpus needed at retirement and the monthly SIP to reach it.
({double corpusNeeded, double monthlyExpenseAtRetirement, double monthlySip}) retirement({
  required double currentMonthlyExpense,
  required int currentAge,
  required int retireAge,
  required int lifeExpectancy,
  required double inflationPct,
  required double preReturnPct,
  required double postReturnPct,
  double currentSavings = 0,
}) {
  final yearsToRetire = retireAge - currentAge;
  final yearsInRetirement = lifeExpectancy - retireAge;
  final expAtRet = currentMonthlyExpense * math.pow(1 + inflationPct / 100, yearsToRetire);
  // Real monthly return after retirement (inflation-adjusted withdrawals).
  final rNom = postReturnPct / 100 / 12;
  final inf = inflationPct / 100 / 12;
  final rReal = (1 + rNom) / (1 + inf) - 1;
  final n = yearsInRetirement * 12;
  final corpus = rReal.abs() < 1e-12 ? expAtRet * n : expAtRet * (1 - math.pow(1 + rReal, -n)) / rReal;
  final fvSavings = currentSavings * math.pow(1 + preReturnPct / 100, yearsToRetire);
  final need = math.max(0.0, corpus - fvSavings);
  final r = preReturnPct / 100 / 12;
  final months = yearsToRetire * 12;
  final factor = r == 0 ? months.toDouble() : ((math.pow(1 + r, months) - 1) / r) * (1 + r);
  return (corpusNeeded: corpus, monthlyExpenseAtRetirement: expAtRet.toDouble(), monthlySip: factor == 0 ? 0 : need / factor);
}

/// GST on an exclusive or inclusive amount.
({double base, double gst, double total}) gst(double amount, double ratePct, {required bool amountIncludesGst}) {
  if (amountIncludesGst) {
    final base = amount / (1 + ratePct / 100);
    return (base: base, gst: amount - base, total: amount);
  }
  final g = amount * ratePct / 100;
  return (base: amount, gst: g, total: amount + g);
}

/// EPF projection: employee 12% of basic, employer's EPF share 3.67% of basic
/// (the rest goes to EPS), monthly credit, interest compounded monthly at
/// annual rate/12 and credited yearly in practice; modelled monthly here.
({double corpus, double employeeTotal, double employerTotal, double interest}) epf({
  required double monthlyBasic,
  required int currentAge,
  required int retireAge,
  required double annualRatePct,
  double salaryGrowthPct = 0,
  double currentBalance = 0,
}) {
  final years = retireAge - currentAge;
  var bal = currentBalance;
  var emp = 0.0, er = 0.0;
  var basic = monthlyBasic;
  final r = annualRatePct / 100 / 12;
  for (var y = 0; y < years; y++) {
    for (var m = 0; m < 12; m++) {
      final e = basic * 0.12;
      final c = basic * 0.0367;
      emp += e;
      er += c;
      bal = (bal + e + c) * (1 + r);
    }
    basic *= 1 + salaryGrowthPct / 100;
  }
  return (corpus: bal, employeeTotal: emp, employerTotal: er, interest: bal - emp - er - currentBalance);
}

/// Income tax for an individual below 60, slabs as notified for FY 2025-26.
/// Excludes surcharge. [deductions] are Chapter VI-A deductions (old regime
/// only); standard deduction is applied automatically.
({double taxable, double tax, double cess, double total}) incomeTax(double grossIncome, {required bool newRegime, double deductions = 0}) {
  double slabTax(double t, List<(double, double)> slabs) {
    // slabs: (upper bound, rate) ascending; last bound infinite.
    var prev = 0.0, tax = 0.0;
    for (final (upper, rate) in slabs) {
      if (t > prev) tax += (math.min(t, upper) - prev) * rate;
      prev = upper;
    }
    return tax;
  }

  final inf = double.infinity;
  double taxable, tax;
  if (newRegime) {
    taxable = math.max(0.0, grossIncome - 75000);
    tax = slabTax(taxable, [(400000, 0.0), (800000, 0.05), (1200000, 0.10), (1600000, 0.15), (2000000, 0.20), (2400000, 0.25), (inf, 0.30)]);
    if (taxable <= 1200000) {
      tax = 0; // Section 87A rebate (new regime)
    } else {
      // Marginal relief: tax cannot exceed income above the rebate limit.
      tax = math.min(tax, taxable - 1200000);
    }
  } else {
    taxable = math.max(0.0, grossIncome - 50000 - deductions);
    tax = slabTax(taxable, [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (inf, 0.30)]);
    if (taxable <= 500000) tax = 0; // Section 87A rebate (old regime)
  }
  final cess = tax * 0.04;
  return (taxable: taxable, tax: tax, cess: cess, total: tax + cess);
}
