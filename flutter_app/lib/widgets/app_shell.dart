import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../core/api/http_client.dart';
import '../core/auth/auth_controller.dart';
import '../core/nav_config.dart';
import '../core/theme.dart';
import 'common.dart';

/// Multibagg-style shell: announcement strip, sticky 64px top nav with
/// grouped menus, content, footer. Mobile gets a drawer + bottom tab bar.
class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.child});
  final Widget child;
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  bool _showBanner = true;
  final _scaffoldKey = GlobalKey<ScaffoldState>();

  @override
  Widget build(BuildContext context) {
    final narrow = isNarrow(context);
    final loc = GoRouterState.of(context).uri.path;
    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.keyK, control: true): () => showSearch(context: context, delegate: StockSearch()),
        const SingleActivator(LogicalKeyboardKey.keyK, meta: true): () => showSearch(context: context, delegate: StockSearch()),
      },
      child: Focus(
        autofocus: true,
        child: Scaffold(
          key: _scaffoldKey,
          drawer: narrow ? const _MobileDrawer() : null,
          bottomNavigationBar: narrow ? _BottomBar(location: loc) : null,
          body: Column(children: [
            if (_showBanner) _Banner(onClose: () => setState(() => _showBanner = false)),
            _TopNav(narrow: narrow, onMenu: () => _scaffoldKey.currentState?.openDrawer()),
            Expanded(
              child: SingleChildScrollView(
                child: Column(children: [
                  ConstrainedBox(
                    constraints: BoxConstraints(minHeight: MediaQuery.sizeOf(context).height - 260),
                    child: widget.child,
                  ),
                  const AppFooter(),
                ]),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.onClose});
  final VoidCallback onClose;
  @override
  Widget build(BuildContext context) {
    return Container(
      color: Palette.primarySubtle,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(children: [
        const Spacer(),
        const StatusPill('Live', tone: Tone.primary),
        const SizedBox(width: 10),
        Flexible(
          child: Text('Quarterly earnings are rolling in — track results by company',
              overflow: TextOverflow.ellipsis, style: AppText.sans(size: 13, weight: FontWeight.w500)),
        ),
        const SizedBox(width: 10),
        TextButton(
          onPressed: () => context.go('/earnings'),
          child: Text('Earnings Tracker →', style: AppText.sans(size: 13, weight: FontWeight.w600, color: Palette.primary)),
        ),
        const Spacer(),
        IconButton(
            iconSize: 18, onPressed: onClose, icon: const Icon(Icons.close, color: Palette.inkSecondary), tooltip: 'Dismiss'),
      ]),
    );
  }
}

class _TopNav extends StatelessWidget {
  const _TopNav({required this.narrow, required this.onMenu});
  final bool narrow;
  final VoidCallback onMenu;
  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      decoration: const BoxDecoration(color: Colors.white, border: Border(bottom: BorderSide(color: Palette.border))),
      padding: EdgeInsets.symmetric(horizontal: narrow ? 8 : 28),
      child: Row(children: [
        if (narrow) IconButton(onPressed: onMenu, icon: const Icon(Icons.menu)),
        InkWell(
          onTap: () => context.go(auth.isAuthenticated ? '/' : '/welcome'),
          child: Row(children: [
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(color: Palette.primary, borderRadius: BorderRadius.circular(7)),
              alignment: Alignment.center,
              child: Text('S', style: AppText.sans(size: 15, weight: FontWeight.w800, color: Colors.white)),
            ),
            const SizedBox(width: 10),
            Text('stockportfolio.in', style: AppText.sans(size: 17, weight: FontWeight.w700, spacing: -0.3)),
          ]),
        ),
        const Spacer(),
        if (!narrow) ...[
          for (final name in topLinks) _GroupMenu(group: navGroups.firstWhere((g) => g.label == name)),
          _LinkButton('Pricing', '/pricing'),
        ],
        const Spacer(),
        IconButton(
          tooltip: 'Search (Ctrl+K)',
          onPressed: () => showSearch(context: context, delegate: StockSearch()),
          icon: const Icon(Icons.search),
        ),
        const SizedBox(width: 4),
        ListenableBuilder(
          listenable: auth,
          builder: (context, _) => auth.isAuthenticated
              ? PopupMenuButton<String>(
                  tooltip: 'Account',
                  onSelected: (v) async {
                    if (v == 'logout') {
                      await auth.logout();
                      if (context.mounted) context.go('/welcome');
                    }
                  },
                  itemBuilder: (_) => [
                    PopupMenuItem(enabled: false, child: Text((auth.user?['email'] ?? 'Signed in').toString())),
                    const PopupMenuItem(value: 'logout', child: Text('Sign out')),
                  ],
                  child: CircleAvatar(
                    radius: 16,
                    backgroundColor: Palette.primarySubtle,
                    child: Text(
                      ((auth.user?['display_name'] ?? auth.user?['email'] ?? 'U').toString().trim().isEmpty
                              ? 'U'
                              : (auth.user?['display_name'] ?? auth.user?['email'] ?? 'U').toString().trim()[0])
                          .toUpperCase(),
                      style: AppText.sans(size: 13, weight: FontWeight.w700, color: Palette.primary),
                    ),
                  ),
                )
              : FilledButton(onPressed: () => context.go('/auth'), child: const Text('Login')),
        ),
      ]),
    );
  }
}

class _LinkButton extends StatelessWidget {
  const _LinkButton(this.label, this.path);
  final String label;
  final String path;
  @override
  Widget build(BuildContext context) => TextButton(
        onPressed: () => context.go(path),
        child: Text(label, style: AppText.sans(size: 14, weight: FontWeight.w500, color: Palette.inkSecondary)),
      );
}

/// Dropdown mega-menu for one nav group.
class _GroupMenu extends StatelessWidget {
  const _GroupMenu({required this.group});
  final NavGroup group;
  @override
  Widget build(BuildContext context) {
    return MenuAnchor(
      style: MenuStyle(
        backgroundColor: const WidgetStatePropertyAll(Colors.white),
        surfaceTintColor: const WidgetStatePropertyAll(Colors.white),
        shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: const BorderSide(color: Palette.border))),
        padding: const WidgetStatePropertyAll(EdgeInsets.all(8)),
      ),
      menuChildren: [
        for (final item in group.items)
          MenuItemButton(
            onPressed: () => context.go(item.path),
            leadingIcon: Icon(item.icon, size: 18, color: Palette.primary),
            child: ConstrainedBox(
              constraints: const BoxConstraints(minWidth: 260, maxWidth: 320),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(item.label, style: AppText.sans(size: 14, weight: FontWeight.w600)),
                Text(item.blurb, style: AppText.sans(size: 12, color: Palette.inkSecondary)),
              ]),
            ),
          ),
      ],
      builder: (context, controller, _) => TextButton.icon(
        onPressed: () => controller.isOpen ? controller.close() : controller.open(),
        iconAlignment: IconAlignment.end,
        icon: const Icon(Icons.keyboard_arrow_down, size: 18, color: Palette.inkSecondary),
        label: Text(group.label, style: AppText.sans(size: 14, weight: FontWeight.w500, color: Palette.inkSecondary)),
      ),
    );
  }
}

class _MobileDrawer extends StatelessWidget {
  const _MobileDrawer();
  @override
  Widget build(BuildContext context) {
    return Drawer(
      backgroundColor: Colors.white,
      child: SafeArea(
        child: ListView(children: [
          for (final g in navGroups)
            ExpansionTile(
              shape: const Border(),
              collapsedShape: const Border(),
              title: Text(g.label, style: AppText.sans(size: 14, weight: FontWeight.w600)),
              children: [
                for (final i in g.items)
                  ListTile(
                    dense: true,
                    leading: Icon(i.icon, size: 18, color: Palette.primary),
                    title: Text(i.label, style: AppText.sans(size: 14)),
                    onTap: () {
                      Navigator.of(context).pop();
                      context.go(i.path);
                    },
                  ),
              ],
            ),
        ]),
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  const _BottomBar({required this.location});
  final String location;
  @override
  Widget build(BuildContext context) {
    const tabs = [
      ('Portfolio', Icons.work_outline, '/'),
      ('Alerts', Icons.notifications_none, '/alerts'),
      ('Ask Iris', Icons.auto_awesome_outlined, '/ask'),
      ('Discovery', Icons.explore_outlined, '/discovery'),
      ('Markets', Icons.public, '/market'),
    ];
    final idx = tabs.indexWhere((t) => t.$3 == '/' ? location == '/' : location.startsWith(t.$3));
    return NavigationBar(
      height: 64,
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.white,
      indicatorColor: Palette.primarySubtle,
      selectedIndex: idx < 0 ? 0 : idx,
      onDestinationSelected: (i) => context.go(tabs[i].$3),
      destinations: [for (final t in tabs) NavigationDestination(icon: Icon(t.$2), label: t.$1)],
    );
  }
}

class AppFooter extends StatelessWidget {
  const AppFooter({super.key});
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: Palette.border))),
      child: PageBox(
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 36),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(spacing: 48, runSpacing: 28, children: [
            for (final g in navGroups)
              SizedBox(
                width: 170,
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(g.label.toUpperCase(), style: AppText.label()),
                  const SizedBox(height: 10),
                  for (final i in g.items.take(7))
                    InkWell(
                      onTap: () => context.go(i.path),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text(i.label, style: AppText.sans(size: 13, color: Palette.inkSecondary)),
                      ),
                    ),
                ]),
              ),
          ]),
          const SizedBox(height: 28),
          const Divider(),
          const SizedBox(height: 16),
          Text(
            'stockportfolio.in provides research tools and analytics for Indian listed companies. It is not a SEBI '
            'registered investment adviser and nothing here is investment advice. Models can be wrong; verify '
            'important information. Prices may be delayed.',
            style: AppText.sans(size: 12, color: Palette.inkSecondary, height: 1.5),
          ),
        ]),
      ),
    );
  }
}

/// Cmd/Ctrl+K stock search backed by /api/stocks/search.
class StockSearch extends SearchDelegate<void> {
  StockSearch() : super(searchFieldLabel: 'Search stocks by name or ticker');

  @override
  List<Widget>? buildActions(BuildContext context) =>
      [if (query.isNotEmpty) IconButton(onPressed: () => query = '', icon: const Icon(Icons.clear))];

  @override
  Widget? buildLeading(BuildContext context) =>
      IconButton(onPressed: () => close(context, null), icon: const Icon(Icons.arrow_back));

  @override
  Widget buildResults(BuildContext context) => buildSuggestions(context);

  @override
  Widget buildSuggestions(BuildContext context) {
    if (query.trim().length < 2) {
      return const EmptyState(icon: Icons.search, title: 'Type at least 2 characters');
    }
    return FutureBuilder(
      future: getJson('/api/stocks/search${queryString({'q': query.trim()})}'),
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const Loading();
        if (snap.hasError) return ErrorState(snap.error!);
        final data = snap.data;
        final list = asList(data is Map ? (data['results'] ?? data['items'] ?? data['stocks']) : data);
        if (list.isEmpty) return const EmptyState(title: 'No matches');
        return ListView(children: [
          for (final r in list)
            ListTile(
              title: Text((asMap(r)['name'] ?? asMap(r)['company'] ?? asMap(r)['symbol'] ?? '').toString(),
                  style: AppText.sans(weight: FontWeight.w600)),
              subtitle: Text((asMap(r)['symbol'] ?? asMap(r)['ticker'] ?? '').toString(), style: AppText.mono(size: 12)),
              onTap: () {
                final t = (asMap(r)['symbol'] ?? asMap(r)['ticker'] ?? '').toString();
                close(context, null);
                if (t.isNotEmpty) context.go('/analyse/${Uri.encodeComponent(t)}');
              },
            ),
        ]);
      },
    );
  }
}
