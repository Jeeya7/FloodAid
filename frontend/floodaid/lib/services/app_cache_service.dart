import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Singleton cache for slow API responses (resources + risk data).
///
/// Two-layer strategy:
///   1. In-memory map  — instant, survives tab switches within a session.
///   2. SharedPreferences — survives app restarts, expires after [_ttl].
///
/// Usage:
///   final cached = await AppCacheService().loadResources();
///   if (cached != null) { /* use it */ } else { /* fetch, then save */ }
class AppCacheService {
  // ── Singleton ────────────────────────────────────────────────────────────
  static final AppCacheService _instance = AppCacheService._internal();
  factory AppCacheService() => _instance;
  AppCacheService._internal();

  // ── Config ───────────────────────────────────────────────────────────────
  static const Duration _ttl = Duration(minutes: 15);

  static const String _resourcesKey    = 'cache_resources';
  static const String _resourcesTsKey  = 'cache_resources_ts';
  static const String _riskKey         = 'cache_risk';
  static const String _riskTsKey       = 'cache_risk_ts';

  // ── In-memory hot cache ───────────────────────────────────────────────────
  Map<String, dynamic>? _resources;
  Map<String, dynamic>? _risk;

  // ── Helpers ───────────────────────────────────────────────────────────────
  bool _isFresh(int? timestampMs) {
    if (timestampMs == null) return false;
    final age = DateTime.now().difference(
      DateTime.fromMillisecondsSinceEpoch(timestampMs),
    );
    return age < _ttl;
  }

  // ── Resources ─────────────────────────────────────────────────────────────

  /// Returns cached resource data if still fresh, otherwise null.
  Future<Map<String, dynamic>?> loadResources() async {
    // 1. Hot cache hit — no disk read needed
    if (_resources != null) return _resources;

    // 2. Disk cache
    final prefs = await SharedPreferences.getInstance();
    final ts    = prefs.getInt(_resourcesTsKey);
    if (_isFresh(ts)) {
      final raw = prefs.getString(_resourcesKey);
      if (raw != null) {
        _resources = jsonDecode(raw) as Map<String, dynamic>;
        return _resources;
      }
    }

    return null; // cache miss — caller must fetch
  }

  /// Persist resource data to both the hot cache and disk.
  Future<void> saveResources(Map<String, dynamic> data) async {
    _resources = data;
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.setString(_resourcesKey, jsonEncode(data)),
      prefs.setInt(_resourcesTsKey, DateTime.now().millisecondsSinceEpoch),
    ]);
  }

  // ── Risk data ─────────────────────────────────────────────────────────────

  /// Returns cached risk data if still fresh, otherwise null.
  Future<Map<String, dynamic>?> loadRisk() async {
    if (_risk != null) return _risk;

    final prefs = await SharedPreferences.getInstance();
    final ts    = prefs.getInt(_riskTsKey);
    if (_isFresh(ts)) {
      final raw = prefs.getString(_riskKey);
      if (raw != null) {
        _risk = jsonDecode(raw) as Map<String, dynamic>;
        return _risk;
      }
    }

    return null;
  }

  /// Persist risk data to both the hot cache and disk.
  Future<void> saveRisk(Map<String, dynamic> data) async {
    _risk = data;
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.setString(_riskKey, jsonEncode(data)),
      prefs.setInt(_riskTsKey, DateTime.now().millisecondsSinceEpoch),
    ]);
  }

  // ── Manual invalidation ───────────────────────────────────────────────────

  /// Force a fresh fetch next time by clearing both layers.
  Future<void> clearAll() async {
    _resources = null;
    _risk      = null;
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.remove(_resourcesKey),
      prefs.remove(_resourcesTsKey),
      prefs.remove(_riskKey),
      prefs.remove(_riskTsKey),
    ]);
  }
}
