import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/auth_controller.dart';
import '../../core/theme.dart';

/// Sign in / sign up. Light, single column, no marketing chrome.
class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key, this.redirect});
  final String? redirect;
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _name = TextEditingController();
  bool _signup = false;
  bool _busy = false;
  String? _error;

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_signup) {
        await auth.signup(_email.text.trim(), _password.text, _name.text.trim());
      } else {
        await auth.signin(_email.text.trim(), _password.text);
      }
      if (mounted) context.go(widget.redirect?.isNotEmpty == true ? widget.redirect! : '/');
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width > 900;
    return Scaffold(
      body: Row(children: [
        if (wide)
          Expanded(
            child: Container(
              decoration: const BoxDecoration(color: Palette.primarySubtle, border: Border(right: BorderSide(color: Palette.border))),
              padding: const EdgeInsets.all(56),
              alignment: Alignment.bottomLeft,
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Know what to buy, sell or hold, and why.',
                    style: AppText.sans(size: 34, weight: FontWeight.w700, height: 1.15, spacing: -0.6)),
                const SizedBox(height: 14),
                Text(
                  'Ranked recommendations with the evidence behind each call, tax-aware exits and portfolio risk in one place.',
                  style: AppText.sans(size: 15, color: Palette.inkSecondary, height: 1.5),
                ),
              ]),
            ),
          ),
        Expanded(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(28),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 400),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  InkWell(
                      onTap: () => context.go('/welcome'),
                      child: Text('stockportfolio.in', style: AppText.sans(size: 17, weight: FontWeight.w700))),
                  const SizedBox(height: 28),
                  Text(_signup ? 'Create your account' : 'Sign in',
                      style: AppText.sans(size: 26, weight: FontWeight.w700, spacing: -0.4)),
                  const SizedBox(height: 6),
                  Text(_signup ? 'Takes under a minute.' : 'Welcome back.',
                      style: AppText.sans(color: Palette.inkSecondary)),
                  const SizedBox(height: 24),
                  if (_signup) ...[
                    TextField(controller: _name, decoration: const InputDecoration(labelText: 'Display name (optional)')),
                    const SizedBox(height: 12),
                  ],
                  TextField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(labelText: 'Email')),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _password,
                    obscureText: true,
                    onSubmitted: (_) => _submit(),
                    decoration: const InputDecoration(labelText: 'Password'),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(color: Palette.sellSurface, borderRadius: BorderRadius.circular(8)),
                      child: Text(_error!, style: AppText.sans(size: 13, color: Palette.sell)),
                    ),
                  ],
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _busy ? null : _submit,
                      child: Text(_busy ? 'Please wait…' : (_signup ? 'Create account' : 'Sign in')),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextButton(
                    onPressed: () => setState(() {
                      _signup = !_signup;
                      _error = null;
                    }),
                    child: Text(_signup ? 'Already have an account? Sign in' : 'New here? Create an account'),
                  ),
                ]),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}
