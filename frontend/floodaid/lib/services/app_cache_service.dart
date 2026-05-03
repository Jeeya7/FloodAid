import 'dart:async';
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Singleton cache with two-layer storage and cross-instance fetch deduplication.
///
/// Layer 1 – In-memory Future lock:  prevents two calls in the same Dart VM
///            (same process) from both hitting the network.
/// Layer 2 – SharedPreferences lock: prevents two browser tabs / processes
///            from both hitting the network simultaneously.
/// Layer 3 – Disk TTL cache:         serves data across app restarts.
class AppCacheService {
  static final AppCacheService _instance = AppCacheService._internal();
  factory AppCacheService() => _instance;
  AppCacheService._internal();

  static const Duration _ttl          = Duration(minutes: 15);
  static const Duration _fetchTimeout = Duration(seconds: 30);

  // Disk keys
  static const _resourcesKey      = 'cache_resources';
  static const _resourcesTsKey    = 'cache_resources_ts';
  static const _resourcesLockKey  = 'cache_resources_lock';
  static const _riskKey           = 'cache_risk';
  static const _riskTsKey         = 'cache_risk_ts';
  static const _riskLockKey       = 'cache_risk_lock';

  // In-memory
  Map<String, dynamic>?            _resources;
  Map<String, dynamic>?            _risk;
  Future<Map<String, dynamic>>?    _resourcesInFlight;
  Future<Map<String, dynamic>>?    _riskInFlight;

  bool _isFresh(int? tsMs) {
    if (tsMs == null) return false;
    return DateTime.now().difference(
      DateTime.fromMillisecondsSinceEpoch(tsMs),
    ) < _ttl;
  }

  bool _lockHeld(int? lockTs) {
    if (lockTs == null) return false;
    return DateTime.now().difference(
      DateTime.fromMillisecondsSinceEpoch(lockTs),
    ) < _fetchTimeout;
  }

  // ── Resources ─────────────────────────────────────────────────────────────

  /// Returns cached data instantly if available, otherwise returns null.
  Future<Map<String, dynamic>?> loadResources() async {
    if (_resources != null) return _resources;
    final prefs = await SharedPreferences.getInstance();
    if (_isFresh(prefs.getInt(_resourcesTsKey))) {
      final raw = prefs.getString(_resourcesKey);
      if (raw != null) {
        _resources = jsonDecode(raw) as Map<String, dynamic>;
        return _resources;
      }
    }
    return null;
  }

  /// Fetches resources exactly once regardless of how many callers ask simultaneously.
  ///
  /// [doFetch] is the HTTP call. It is only ever invoked once per cache miss —
  /// all concurrent callers await the same Future.
  Future<Map<String, dynamic>> getOrFetchResources(
    Future<Map<String, dynamic>> Function() doFetch,
  ) async {
    // Layer 1: in-memory hit
    if (_resources != null) return _resources!;

    // Layer 2: disk hit
    final cached = await loadResources();
    if (cached != null) return cached;

    // Layer 3: in-process Future lock (same Dart VM)
    if (_resourcesInFlight != null) return _resourcesInFlight!;

    // Layer 4: cross-process SharedPreferences lock (multiple tabs/processes)
    final prefs  = await SharedPreferences.getInstance();
    final lockTs = prefs.getInt(_resourcesLockKey);
    if (_lockHeld(lockTs)) {
      // Another process is fetching; poll disk until it writes the result.
      return _pollUntilReady(
        load:    loadResources,
        timeout: _fetchTimeout,
      );
    }

    // This instance wins the race — acquire lock and fetch.
    await prefs.setInt(_resourcesLockKey, DateTime.now().millisecondsSinceEpoch);

    _resourcesInFlight = doFetch().then((data) async {
      _resources = data;
      final p = await SharedPreferences.getInstance();
      await Future.wait([
        p.setString(_resourcesKey,   jsonEncode(data)),
        p.setInt(_resourcesTsKey,    DateTime.now().millisecondsSinceEpoch),
        p.remove(_resourcesLockKey),
      ]);
      return data;
    }).whenComplete(() => _resourcesInFlight = null);

    return _resourcesInFlight!;
  }

  Future<void> saveResources(Map<String, dynamic> data) async {
    _resources = data;
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.setString(_resourcesKey, jsonEncode(data)),
      prefs.setInt(_resourcesTsKey,  DateTime.now().millisecondsSinceEpoch),
    ]);
  }

  // ── Risk ──────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>?> loadRisk() async {
    if (_risk != null) return _risk;
    final prefs = await SharedPreferences.getInstance();
    if (_isFresh(prefs.getInt(_riskTsKey))) {
      final raw = prefs.getString(_riskKey);
      if (raw != null) {
        _risk = jsonDecode(raw) as Map<String, dynamic>;
        return _risk;
      }
    }
    return null;
  }

  Future<Map<String, dynamic>> getOrFetchRisk(
    Future<Map<String, dynamic>> Function() doFetch,
  ) async {
    if (_risk != null) return _risk!;

    final cached = await loadRisk();
    if (cached != null) return cached;

    if (_riskInFlight != null) return _riskInFlight!;

    final prefs  = await SharedPreferences.getInstance();
    final lockTs = prefs.getInt(_riskLockKey);
    if (_lockHeld(lockTs)) {
      return _pollUntilReady(load: loadRisk, timeout: _fetchTimeout);
    }

    await prefs.setInt(_riskLockKey, DateTime.now().millisecondsSinceEpoch);

    _riskInFlight = doFetch().then((data) async {
      _risk = data;
      final p = await SharedPreferences.getInstance();
      await Future.wait([
        p.setString(_riskKey,  jsonEncode(data)),
        p.setInt(_riskTsKey,   DateTime.now().millisecondsSinceEpoch),
        p.remove(_riskLockKey),
      ]);
      return data;
    }).whenComplete(() => _riskInFlight = null);

    return _riskInFlight!;
  }

  Future<void> saveRisk(Map<String, dynamic> data) async {
    _risk = data;
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.setString(_riskKey, jsonEncode(data)),
      prefs.setInt(_riskTsKey,  DateTime.now().millisecondsSinceEpoch),
    ]);
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  /// Polls [load] every 500 ms until it returns non-null or [timeout] elapses.
  Future<Map<String, dynamic>> _pollUntilReady({
    required Future<Map<String, dynamic>?> Function() load,
    required Duration timeout,
  }) async {
    final deadline = DateTime.now().add(timeout);
    while (DateTime.now().isBefore(deadline)) {
      await Future.delayed(const Duration(milliseconds: 500));
      final data = await load();
      if (data != null) return data;
    }
    throw TimeoutException('Waited for another fetch to complete but timed out.');
  }

  // ── Invalidation ──────────────────────────────────────────────────────────

  Future<void> clearAll() async {
    _resources        = null;
    _risk             = null;
    _resourcesInFlight = null;
    _riskInFlight     = null;
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.remove(_resourcesKey),
      prefs.remove(_resourcesTsKey),
      prefs.remove(_resourcesLockKey),
      prefs.remove(_riskKey),
      prefs.remove(_riskTsKey),
      prefs.remove(_riskLockKey),
    ]);
  }
}
