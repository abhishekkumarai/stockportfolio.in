import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';
import '../storage.dart';

/// Port of frontend/src/lib/http.ts: same headers, same error contract.
class ApiException implements Exception {
  ApiException(this.message, [this.status]);
  final String message;
  final int? status;
  @override
  String toString() => message;
}

Map<String, String> _headers({bool body = false, bool account = false}) {
  final h = <String, String>{};
  if (body) h['Content-Type'] = 'application/json';
  final fyers = prefs.getString(fyersTokenKey);
  if (fyers != null && fyers.isNotEmpty) h['X-Fyers-Token'] = fyers;
  if (account) {
    final key = prefs.getString(accountKey);
    if (key != null && key.isNotEmpty) h['X-Account-Key'] = key;
  }
  return h;
}

dynamic _handle(http.Response r) {
  if (r.statusCode < 200 || r.statusCode >= 300) {
    var detail = 'Request failed (${r.statusCode})';
    try {
      final b = jsonDecode(r.body);
      final d = b is Map ? b['detail'] : null;
      if (d is String) {
        detail = d;
      } else if (d is Map) {
        detail = (d['reason'] ?? jsonEncode(d)).toString();
      }
    } catch (_) {}
    throw ApiException(detail, r.statusCode);
  }
  if (r.body.isEmpty) return null;
  return jsonDecode(utf8.decode(r.bodyBytes));
}

/// Query string from a sparse map; null / empty values dropped, lists repeated.
String queryString(Map<String, Object?> params) {
  final parts = <String>[];
  params.forEach((k, v) {
    if (v == null || v == '') return;
    if (v is Iterable) {
      for (final e in v) {
        parts.add('${Uri.encodeQueryComponent(k)}=${Uri.encodeQueryComponent('$e')}');
      }
    } else {
      parts.add('${Uri.encodeQueryComponent(k)}=${Uri.encodeQueryComponent('$v')}');
    }
  });
  return parts.isEmpty ? '' : '?${parts.join('&')}';
}

Future<dynamic> getJson(String path, {bool account = false}) async =>
    _handle(await http.get(Uri.parse(apiUrl(path)), headers: _headers(account: account)));

Future<dynamic> postJson(String path, Object? body, {bool account = false}) async =>
    _handle(await http.post(Uri.parse(apiUrl(path)),
        headers: _headers(body: true, account: account), body: jsonEncode(body)));

/// Convenience accessors for loosely typed JSON.
typedef Json = Map<String, dynamic>;
Json asMap(dynamic v) => v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};
List<dynamic> asList(dynamic v) => v is List ? v : const [];
double? asNum(dynamic v) => v is num ? v.toDouble() : (v is String ? double.tryParse(v) : null);
