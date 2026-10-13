import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../widgets/common.dart';
import 'calc.dart' as c;

class _Field {
  const _Field(this.key, this.label, this.initial);
  final String key, label, initial;
}

class _Spec {
  const _Spec(this.slug, this.title, this.blurb, this.fields, this.compute, {this.toggle});
  final String slug, title, blurb;
  final List<_Field> fields;
  final List<(String, String)> Function(Map<String, double> v, bool toggled) compute;
  final (String off, String on)? toggle;
}

String _inr(double v) => fmtInr(v);
String _pct(double v) => '${v.toStringAsFixed(2)}%';

final _specs = <_Spec>[
  _Spec('sip', 'SIP calculator', 'What a monthly investment grows to.', const [
    _Field('m', 'Monthly investment (₹)', '10000'),
    _Field('r', 'Expected return (% p.a.)', '12'),
    _Field('y', 'Years', '10'),
  ], (v, _) {
    final r = c.sip(v['m']!, v['r']!, v['y']!);
    return [('Invested', _inr(r.invested)), ('Estimated gain', _inr(r.gain)), ('Future value', _inr(r.futureValue))];
  }),
  _Spec('lumpsum', 'Lumpsum calculator', 'Growth of a one-time investment.', const [
    _Field('a', 'Amount (₹)', '100000'),
    _Field('r', 'Expected return (% p.a.)', '12'),
    _Field('y', 'Years', '10'),
  ], (v, _) {
    final r = c.lumpsum(v['a']!, v['r']!, v['y']!);
    return [('Invested', _inr(r.invested)), ('Estimated gain', _inr(r.gain)), ('Future value', _inr(r.futureValue))];
  }),
  _Spec('swp', 'SWP calculator', 'How long a corpus lasts with monthly withdrawals.', const [
    _Field('c', 'Corpus (₹)', '5000000'),
    _Field('w', 'Monthly withdrawal (₹)', '30000'),
    _Field('r', 'Expected return (% p.a.)', '8'),
    _Field('y', 'Years', '20'),
  ], (v, _) {
    final r = c.swp(v['c']!, v['w']!, v['r']!, v['y']!);
    return [
      ('Total withdrawn', _inr(r.withdrawn)),
      ('Corpus remaining', _inr(r.remaining)),
      ('Runs out', r.exhaustedMonth == null ? 'Not within the period' : 'Month ${r.exhaustedMonth}'),
    ];
  }),
  _Spec('ppf', 'PPF calculator', 'Yearly deposits compounded annually.', const [
    _Field('d', 'Yearly deposit (₹, max 1,50,000)', '150000'),
    _Field('r', 'Interest rate (% p.a.)', '7.1'),
    _Field('y', 'Years (min 15)', '15'),
  ], (v, _) {
    final r = c.ppf(v['d']!, v['r']!, v['y']!.round());
    return [('Invested', _inr(r.invested)), ('Interest earned', _inr(r.interest)), ('Maturity value', _inr(r.maturity))];
  }),
  _Spec('fd', 'Fixed deposit calculator', 'Maturity with quarterly compounding.', const [
    _Field('p', 'Deposit (₹)', '100000'),
    _Field('r', 'Interest rate (% p.a.)', '7'),
    _Field('y', 'Years', '5'),
  ], (v, _) {
    final r = c.fd(v['p']!, v['r']!, v['y']!);
    return [('Interest earned', _inr(r.interest)), ('Maturity value', _inr(r.maturity))];
  }),
  _Spec('cagr', 'CAGR calculator', 'Compound annual growth between two values.', const [
    _Field('b', 'Beginning value (₹)', '100000'),
    _Field('e', 'Ending value (₹)', '200000'),
    _Field('y', 'Years', '5'),
  ], (v, _) {
    final r = c.cagr(v['b']!, v['e']!, v['y']!);
    return [('CAGR', r.isNaN ? 'Enter positive values' : _pct(r))];
  }),
  _Spec('hra', 'HRA exemption', 'Exempt HRA is the least of three amounts (annual figures).', const [
    _Field('b', 'Basic + DA, yearly (₹)', '600000'),
    _Field('h', 'HRA received, yearly (₹)', '240000'),
    _Field('r', 'Rent paid, yearly (₹)', '300000'),
  ], (v, metro) {
    final x = c.hraExemption(basicPlusDa: v['b']!, hraReceived: v['h']!, rentPaid: v['r']!, metro: metro);
    return [('Exempt HRA', _inr(x)), ('Taxable HRA', _inr(v['h']! - x))];
  }, toggle: ('Non-metro (40%)', 'Metro (50%)')),
  _Spec('retirement', 'Retirement planner', 'The corpus you need and the SIP that gets you there.', const [
    _Field('e', 'Current monthly expense (₹)', '50000'),
    _Field('a', 'Current age', '30'),
    _Field('ra', 'Retirement age', '60'),
    _Field('l', 'Life expectancy', '85'),
    _Field('i', 'Inflation (% p.a.)', '6'),
    _Field('pre', 'Return before retirement (%)', '12'),
    _Field('post', 'Return after retirement (%)', '8'),
    _Field('s', 'Current savings (₹)', '0'),
  ], (v, _) {
    final r = c.retirement(
        currentMonthlyExpense: v['e']!,
        currentAge: v['a']!.round(),
        retireAge: v['ra']!.round(),
        lifeExpectancy: v['l']!.round(),
        inflationPct: v['i']!,
        preReturnPct: v['pre']!,
        postReturnPct: v['post']!,
        currentSavings: v['s']!);
    return [('Monthly expense at retirement', _inr(r.monthlyExpenseAtRetirement)), ('Corpus needed', _inr(r.corpusNeeded)), ('Monthly SIP required', _inr(r.monthlySip))];
  }),
  _Spec('gst', 'GST calculator', 'Add or remove GST.', const [
    _Field('a', 'Amount (₹)', '1000'),
    _Field('r', 'GST rate (%)', '18'),
  ], (v, inc) {
    final r = c.gst(v['a']!, v['r']!, amountIncludesGst: inc);
    return [('Base amount', _inr(r.base)), ('GST', _inr(r.gst)), ('Total', _inr(r.total))];
  }, toggle: ('Amount excludes GST', 'Amount includes GST')),
  _Spec('epf', 'EPF calculator', 'Projected provident fund balance (12% employee, 3.67% employer EPF share).', const [
    _Field('b', 'Monthly basic (₹)', '50000'),
    _Field('a', 'Current age', '30'),
    _Field('ra', 'Retirement age', '58'),
    _Field('r', 'Interest rate (% p.a.)', '8.25'),
    _Field('g', 'Salary growth (% p.a.)', '5'),
    _Field('c', 'Current EPF balance (₹)', '0'),
  ], (v, _) {
    final r = c.epf(
        monthlyBasic: v['b']!,
        currentAge: v['a']!.round(),
        retireAge: v['ra']!.round(),
        annualRatePct: v['r']!,
        salaryGrowthPct: v['g']!,
        currentBalance: v['c']!);
    return [('Employee contributions', _inr(r.employeeTotal)), ('Employer contributions', _inr(r.employerTotal)), ('Interest', _inr(r.interest)), ('Corpus at retirement', _inr(r.corpus))];
  }),
  _Spec('income-tax', 'Income tax', 'FY 2025-26 slabs for an individual under 60, excluding surcharge. Verify before filing.', const [
    _Field('g', 'Gross income, yearly (₹)', '1500000'),
    _Field('d', 'Deductions, old regime only (₹)', '150000'),
  ], (v, newRegime) {
    final r = c.incomeTax(v['g']!, newRegime: newRegime, deductions: v['d']!);
    return [('Taxable income', _inr(r.taxable)), ('Tax', _inr(r.tax)), ('Health & education cess (4%)', _inr(r.cess)), ('Total tax', _inr(r.total))];
  }, toggle: ('Old regime', 'New regime')),
];

class CalculatorsHubPage extends StatelessWidget {
  const CalculatorsHubPage({super.key});
  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'Calculators',
      subtitle: 'Plain arithmetic, computed on your device. Nothing here is advice.',
      children: [
        ResponsiveGrid(columns: 3, children: [
          for (final s in _specs)
            InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => context.go('/calculators/${s.slug}'),
              child: Panel(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(s.title, style: AppText.sans(size: 16, weight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  Text(s.blurb, style: AppText.sans(size: 13, color: Palette.inkSecondary, height: 1.45)),
                ]),
              ),
            ),
        ]),
      ],
    );
  }
}

class CalculatorPage extends StatefulWidget {
  const CalculatorPage({super.key, required this.slug});
  final String slug;
  @override
  State<CalculatorPage> createState() => _CalculatorPageState();
}

class _CalculatorPageState extends State<CalculatorPage> {
  late _Spec spec = _specs.firstWhere((s) => s.slug == widget.slug, orElse: () => _specs.first);
  late final Map<String, TextEditingController> ctl = {for (final f in spec.fields) f.key: TextEditingController(text: f.initial)};
  bool toggled = true;

  @override
  Widget build(BuildContext context) {
    final values = {for (final f in spec.fields) f.key: double.tryParse(ctl[f.key]!.text) ?? 0.0};
    List<(String, String)> out;
    try {
      out = spec.compute(values, toggled);
    } catch (_) {
      out = const [('Result', 'Check your inputs')];
    }
    return PageScaffold(
      title: spec.title,
      subtitle: spec.blurb,
      actions: [OutlinedButton(onPressed: () => context.go('/calculators'), child: const Text('All calculators'))],
      children: [
        ResponsiveGrid(columns: 2, children: [
          Panel(
            title: 'Inputs',
            child: Column(children: [
              if (spec.toggle != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: SegTabs(labels: [spec.toggle!.$1, spec.toggle!.$2], index: toggled ? 1 : 0, onChanged: (i) => setState(() => toggled = i == 1)),
                ),
              for (final f in spec.fields)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: TextField(
                    controller: ctl[f.key],
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: InputDecoration(labelText: f.label),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
            ]),
          ),
          Panel(
            title: 'Result',
            child: Column(children: [
              for (final (k, v) in out)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Row(children: [
                    Expanded(child: Text(k, style: AppText.sans(size: 14, color: Palette.inkSecondary))),
                    Text(v, style: AppText.mono(size: 16, weight: FontWeight.w600)),
                  ]),
                ),
            ]),
          ),
        ]),
      ],
    );
  }
}
