import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../api/http_client.dart';
import '../config.dart';
import '../storage.dart';

/// Port of frontend/src/lib/auth.ts. A ChangeNotifier so go_router can
/// refresh redirects on sign-in / sign-out (replaces the `auth-changed` event).
class AuthController extends ChangeNotifier {
  Json? user;

  String? get token => prefs.getString(tokenKey);
  bool get isAuthenticated => (token ?? '').isNotEmpty;

  void load() {
    final raw = prefs.getString(userKey);
    if (raw != null) {
      try {
        user = asMap(jsonDecode(raw));
      } catch (_) {}
    }
  }

  Future<void> _save(String token, Json u) async {
    await prefs.setString(tokenKey, token);
    await prefs.setString(userKey, jsonEncode(u));
    await prefs.setString(accountKey, token);
    user = u;
    notifyListeners();
  }

  Future<void> _clear() async {
    await prefs.remove(tokenKey);
    await prefs.remove(userKey);
    await prefs.remove(accountKey);
    user = null;
    notifyListeners();
  }

  Future<void> _authCall(String path, Json body, String failure) async {
    final r = await http.post(Uri.parse(apiUrl(path)),
        headers: {'Content-Type': 'application/json'}, body: jsonEncode(body));
    if (r.statusCode < 200 || r.statusCode >= 300) {
      var msg = '$failure (${r.statusCode})';
      try {
        final d = asMap(jsonDecode(r.body))['detail'];
        if (d != null) msg = d is String ? d : jsonEncode(d);
      } catch (_) {}
      throw ApiException(msg, r.statusCode);
    }
    final data = asMap(jsonDecode(r.body));
    await _save(data['token'] as String, asMap(data['user']));
  }

  Future<void> signin(String email, String password) =>
      _authCall('/api/auth/signin', {'email': email, 'password': password}, 'Sign in failed');

  Future<void> signup(String email, String password, [String? displayName]) =>
      _authCall(
          '/api/auth/signup',
          {
            'email': email,
            'password': password,
            if (displayName != null && displayName.isNotEmpty) 'display_name': displayName,
          },
          'Registration failed');

  Future<void> logout() async {
    final t = token;
    if (t != null) {
      try {
        await http.post(Uri.parse(apiUrl('/api/auth/logout')), headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $t',
          'X-Account-Key': t,
        });
      } catch (_) {}
    }
    await _clear();
  }

  Future<void> refreshUser() async {
    final t = token;
    if (t == null) return;
    try {
      final r = await http.get(Uri.parse(apiUrl('/api/auth/me')),
          headers: {'Authorization': 'Bearer $t', 'X-Account-Key': t});
      if (r.statusCode == 401) {
        await _clear();
      } else if (r.statusCode == 200) {
        final u = asMap(jsonDecode(r.body))['user'];
        if (u != null) {
          user = asMap(u);
          await prefs.setString(userKey, jsonEncode(user));
          notifyListeners();
        }
      }
    } catch (_) {}
  }
}

final auth = AuthController();
