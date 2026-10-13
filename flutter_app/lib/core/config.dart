/// API base URL, injected at build time:
/// `flutter build web --dart-define=API_URL=https://api.example.com`.
/// Mirrors frontend/src/lib/api.ts: release builds must set it explicitly.
const String _configured = String.fromEnvironment('API_URL');

String _resolve() {
  const isRelease = bool.fromEnvironment('dart.vm.product');
  if (_configured.isEmpty) {
    if (isRelease) {
      throw StateError(
          'API_URL is not set. Build with --dart-define=API_URL=https://...');
    }
    return 'http://127.0.0.1:8001';
  }
  if (!RegExp(r'^https?://').hasMatch(_configured)) {
    throw StateError(
        'API_URL must start with http:// or https:// - got "$_configured".');
  }
  return _configured.replaceAll(RegExp(r'/+$'), '');
}

final String apiBase = _resolve();

String apiUrl(String path) => '$apiBase${path.startsWith('/') ? path : '/$path'}';
