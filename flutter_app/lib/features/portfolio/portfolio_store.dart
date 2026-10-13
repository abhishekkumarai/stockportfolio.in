import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../../core/api/http_client.dart';
import '../../core/config.dart';
import '../../core/storage.dart';

/// Port of the portfolio half of frontend/src/lib/portfolioApi.ts plus the
/// provider in portfolio/layout.tsx: holdings persisted locally, valuation /
/// danger / growth analysis fetched from the backend.
const _storageKey = 'stockportfolio.holdings.v1';

class StoredPortfolio {
  StoredPortfolio({List<Json>? equity, List<Json>? funds, this.cash = 0})
      : equity = equity ?? [],
        funds = funds ?? [];
  final List<Json> equity; // {symbol, quantity, avg_cost, buy_date?}
  final List<Json> funds; // {scheme_code, units, avg_nav, buy_date?, scheme_name?}
  double cash;

  bool get isEmpty => equity.isEmpty && funds.isEmpty;

  Json toJson() => {'equity': equity, 'funds': funds, 'cash': cash};

  static StoredPortfolio fromJson(dynamic raw) {
    final m = asMap(raw);
    return StoredPortfolio(
      equity: asList(m['equity']).map((e) => asMap(e)).toList(),
      funds: asList(m['funds']).map((e) => asMap(e)).toList(),
      cash: asNum(m['cash']) ?? 0,
    );
  }
}

class PortfolioStore extends ChangeNotifier {
  StoredPortfolio portfolio = StoredPortfolio();
  Json? valuation;
  Json? danger;
  Json? growth;
  bool loading = false;
  Object? error;
  bool _loaded = false;

  void ensureLoaded() {
    if (_loaded) return;
    _loaded = true;
    final raw = prefs.getString(_storageKey);
    if (raw != null) {
      try {
        portfolio = StoredPortfolio.fromJson(jsonDecode(raw));
      } catch (_) {}
    }
    refresh();
  }

  Future<void> save(StoredPortfolio p) async {
    portfolio = p;
    await prefs.setString(_storageKey, jsonEncode(p.toJson()));
    notifyListeners();
    await refresh();
  }

  Future<void> refresh() async {
    if (portfolio.isEmpty) {
      valuation = danger = growth = null;
      error = null;
      loading = false;
      notifyListeners();
      return;
    }
    loading = true;
    error = null;
    notifyListeners();
    try {
      final r = asMap(await postJson('/api/portfolio/analyse', portfolio.toJson()));
      valuation = asMap(r['valuation']);
      danger = asMap(r['danger']);
      growth = asMap(r['growth']);
    } catch (e) {
      error = e;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> addEquity(String symbol, double qty, double avgCost, String? buyDate) {
    final p = portfolio;
    p.equity.add({
      'symbol': symbol.trim().toUpperCase(),
      'quantity': qty,
      'avg_cost': avgCost,
      if (buyDate != null && buyDate.isNotEmpty) 'buy_date': buyDate,
    });
    return save(p);
  }

  Future<void> removeEquity(int i) {
    final p = portfolio..equity.removeAt(i);
    return save(p);
  }

  Future<void> removeFund(int i) {
    final p = portfolio..funds.removeAt(i);
    return save(p);
  }

  Future<void> setCash(double cash) => save(portfolio..cash = cash);

  /// Upload a broker statement (xlsx/csv); on success replaces the holdings.
  Future<String> uploadStatement(String filename, Uint8List bytes) async {
    final req = http.MultipartRequest('POST', Uri.parse(apiUrl('/api/portfolio/upload-statement')))
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final res = await http.Response.fromStream(await req.send());
    if (res.statusCode < 200 || res.statusCode >= 300) {
      var msg = 'Upload failed (${res.statusCode})';
      try {
        final d = asMap(jsonDecode(res.body))['detail'];
        if (d is String) msg = d;
      } catch (_) {}
      throw ApiException(msg, res.statusCode);
    }
    final r = asMap(jsonDecode(res.body));
    await save(StoredPortfolio.fromJson(r['portfolio']));
    final rep = asMap(r['report']);
    return 'Imported ${rep['equities_imported'] ?? 0} equities and ${rep['funds_imported'] ?? 0} funds.';
  }
}

final portfolioStore = PortfolioStore();

// ---- stateless calls -------------------------------------------------------

Future<Json> rebalance(StoredPortfolio p, {double cashInflow = 0, String mode = 'zero_tax_inflow'}) async =>
    asMap(await postJson('/api/portfolio/rebalance', {
      'portfolio': p.toJson(),
      'cash_inflow': cashInflow,
      'drift_tolerance': 0.05,
      'mode': mode,
    }));

Future<Json> portfolioNews(StoredPortfolio p) async =>
    asMap(await postJson('/api/portfolio/news', {'equity': p.equity, 'funds': p.funds, 'cash': 0}));

Future<Json> fyersStatus() async => asMap(await getJson('/api/fyers/status'));
Future<Json> fyersHoldings() async => asMap(await getJson('/api/fyers/holdings'));
