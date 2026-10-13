import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// DESIGN.md v2 tokens (kept in v3). Colour carries financial meaning only:
/// buy/gain = emerald, sell/loss = crimson, hold = amber; sapphire = action.
class Palette {
  static const canvas = Color(0xFFF8FAFC);
  static const card = Colors.white;
  static const subtle = Color(0xFFF1F5F9);
  static const border = Color(0xFFE2E8F0);
  static const borderStrong = Color(0xFFCBD5E1);
  static const ink = Color(0xFF0F172A);
  static const inkSecondary = Color(0xFF475569);
  static const inkMuted = Color(0xFF94A3B8);
  static const primary = Color(0xFF2563EB);
  static const primaryHover = Color(0xFF1D4ED8);
  static const primarySubtle = Color(0xFFEFF6FF);
  static const buy = Color(0xFF059669);
  static const buySurface = Color(0xFFECFDF5);
  static const sell = Color(0xFFDC2626);
  static const sellSurface = Color(0xFFFEF2F2);
  static const hold = Color(0xFFD97706);
  static const holdSurface = Color(0xFFFFFBEB);
}

class AppText {
  static TextStyle sans({
    double size = 14,
    FontWeight weight = FontWeight.w400,
    Color color = Palette.ink,
    double? height,
    double? spacing,
  }) =>
      GoogleFonts.publicSans(
          fontSize: size, fontWeight: weight, color: color, height: height, letterSpacing: spacing);

  /// Tabular monospace for every amount, percentage and ratio.
  static TextStyle mono({double size = 13, FontWeight weight = FontWeight.w500, Color color = Palette.ink}) =>
      GoogleFonts.jetBrainsMono(fontSize: size, fontWeight: weight, color: color);

  static TextStyle label({Color color = Palette.inkSecondary}) =>
      sans(size: 11, weight: FontWeight.w600, color: color, spacing: 0.8);
}

ThemeData buildTheme() {
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    scaffoldBackgroundColor: Palette.canvas,
    colorScheme: ColorScheme.fromSeed(
      seedColor: Palette.primary,
      primary: Palette.primary,
      surface: Palette.card,
      error: Palette.sell,
    ),
  );
  OutlineInputBorder outline(Color c, [double w = 1]) => OutlineInputBorder(
      borderRadius: BorderRadius.circular(8), borderSide: BorderSide(color: c, width: w));
  return base.copyWith(
    textTheme: base.textTheme.apply(
      fontFamily: GoogleFonts.publicSans().fontFamily,
      bodyColor: Palette.inkSecondary,
      displayColor: Palette.ink,
    ),
    dividerTheme: const DividerThemeData(color: Palette.border, space: 1, thickness: 1),
    inputDecorationTheme: InputDecorationTheme(
      isDense: true,
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      border: outline(Palette.borderStrong),
      enabledBorder: outline(Palette.borderStrong),
      focusedBorder: outline(Palette.primary, 1.5),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: Palette.primary,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        textStyle: AppText.sans(size: 14, weight: FontWeight.w600, color: Colors.white),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: Palette.ink,
        side: const BorderSide(color: Palette.borderStrong),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        textStyle: AppText.sans(size: 14, weight: FontWeight.w600),
      ),
    ),
  );
}

/// Indian digit grouping (12,34,567.89).
String fmtNum(num? v, {int dp = 2}) {
  if (v == null) return '-';
  final neg = v < 0;
  final parts = v.abs().toStringAsFixed(dp).split('.');
  var whole = parts[0];
  if (whole.length > 3) {
    final last3 = whole.substring(whole.length - 3);
    var rest = whole.substring(0, whole.length - 3);
    final grp = <String>[];
    while (rest.length > 2) {
      grp.insert(0, rest.substring(rest.length - 2));
      rest = rest.substring(0, rest.length - 2);
    }
    if (rest.isNotEmpty) grp.insert(0, rest);
    whole = '${grp.join(',')},$last3';
  }
  return '${neg ? '-' : ''}$whole${dp > 0 ? '.${parts[1]}' : ''}';
}

String fmtInr(num? v, {int dp = 0}) => v == null ? '-' : '₹${fmtNum(v, dp: dp)}';
String fmtPct(num? v, {int dp = 2, bool sign = true}) =>
    v == null ? '-' : '${sign && v > 0 ? '+' : ''}${v.toStringAsFixed(dp)}%';
Color deltaColor(num? v) => v == null || v == 0 ? Palette.inkSecondary : (v > 0 ? Palette.buy : Palette.sell);
