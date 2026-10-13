import 'package:shared_preferences/shared_preferences.dart';

/// Single SharedPreferences instance, loaded once in main().
late final SharedPreferences prefs;

Future<void> initStorage() async {
  prefs = await SharedPreferences.getInstance();
}

const tokenKey = 'stockportfolio_token';
const userKey = 'stockportfolio_user';
const accountKey = 'stockportfolio.account_key';
const fyersTokenKey = 'stockportfolio.fyers_token';
