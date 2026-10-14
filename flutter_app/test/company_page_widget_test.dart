import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:stockportfolio/core/storage.dart';
import 'package:stockportfolio/features/research/company_page.dart';

Map<String, dynamic> _series(int n, {String step = 'day'}) => {
      'data': [
        for (var i = 0; i < n; i++)
          {
            'date': DateTime(2020, 1, 1).add(Duration(days: step == 'day' ? i : i * 30)).toIso8601String(),
            'close': 1000.0 + i,
          }
      ]
    };

http.Response _json(Object o) => http.Response(jsonEncode(o), 200, headers: {'content-type': 'application/json'});

MockClient _client() => MockClient((req) async {
      final p = req.url.path;
      if (p.endsWith('/analyse')) {
        return _json({
          'name': 'Test Co',
          'price': 1234.5,
          'change_pct': 1.2,
          'details': {'day_high': 1240, 'day_low': 1200, 'volume': 5000, 'fifty_two_week_high': 1500, 'fifty_two_week_low': 900},
          'technicals': {'rsi': 55.1, 'rsi_desc': 'Neutral RSI', 'sma20': 1200, 'sma50': 1180, 'sma200': 1100, 'trend': 'Bullish'},
          'sentiment': {'compound': 0.1, 'desc': 'Positive'},
          'recommendation': {'score': 60, 'decision': 'BUY', 'interpretation': 'Constructive.'},
          'chart_data': [for (var i = 0; i < 22; i++) {'date': 'Jan ${i + 1}', 'close': 1000.0 + i, 'high': 1010.0 + i, 'low': 990.0 + i, 'volume': 100}],
          'news': [
            {'title': 'Headline', 'source': 'Src', 'time': 'today'}
          ],
        });
      }
      if (p.endsWith('/history')) {
        return _json(req.url.queryParameters['interval'] == '1mo' ? _series(130, step: 'month') : _series(250));
      }
      if (p.endsWith('/fundamentals')) {
        return _json({
          'fundamentals': {'available': true, 'sector': 'IT', 'market_cap_cr': 1200000, 'pe_ratio': 25.1, 'roce_pct': 50.2, 'roe_pct': 45.0, 'source': 'screener'},
          'scorecard': {
            'score': 70,
            'signals': [
              {'key': 'pe', 'score': 70, 'reason': 'P/E 25 is reasonable', 'available': true},
              {'key': 'roce', 'score': 20, 'reason': 'ROCE weak', 'available': true},
            ],
          },
        });
      }
      return http.Response('not found', 404);
    });

void main() {
  setUpAll(() async {
    SharedPreferences.setMockInitialValues({});
    await initStorage();
  });

  testWidgets('Overview tab renders loaded data without layout errors or a runaway frame loop', (tester) async {
    tester.view.physicalSize = const Size(1400, 1800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await http.runWithClient(() async {
      await tester.pumpWidget(const MaterialApp(home: Scaffold(body: SingleChildScrollView(child: CompanyPage(ticker: 'TEST')))));
      // Not pumpAndSettle: the loading spinner animates forever. Step a bounded number of frames instead.
      for (var i = 0; i < 40; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
    }, _client);

    expect(tester.takeException(), isNull);
    expect(find.text('Test Co'), findsOneWidget);
    expect(find.text('Returns'), findsOneWidget);
    expect(find.text('Investment checklist'), findsOneWidget);
    expect(find.text('Pass'), findsOneWidget);
    expect(find.text('Fail'), findsOneWidget);
  });
}
