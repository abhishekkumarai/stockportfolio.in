import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_web_plugins/url_strategy.dart';

import 'core/auth/auth_controller.dart';
import 'core/storage.dart';
import 'core/theme.dart';
import 'router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  usePathUrlStrategy();
  await initStorage();
  auth.load();
  // Validate the stored session in the background; a 401 clears it and the
  // router guard redirects to /auth.
  auth.refreshUser();
  runApp(const ProviderScope(child: StockPortfolioApp()));
}

class StockPortfolioApp extends StatelessWidget {
  const StockPortfolioApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'stockportfolio.in',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      routerConfig: appRouter,
    );
  }
}
