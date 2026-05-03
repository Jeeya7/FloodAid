import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../map/map_screen.dart';
import '../chat/chat_screen.dart';
import '../resources/resources_screen.dart';
import '../services/app_cache_service.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;

  // Demo mode uses Newport, OR coords instead of GPS
  bool _demoMode = false;
  static const _newportLat = 44.6368;
  static const _newportLng = -124.0535;

 

  // Shared app data — fetched once, passed to all screens
  LatLng?               _userLocation;
  Map<String, dynamic>? _resourcesData;
  Map<String, dynamic>? _riskData;
  bool                  _loadingResources = true;
  bool                  _loadingRisk      = true;
  String                _resourcesError   = '';

  // Static: survives State recreation; resets on hot restart / process exit.
  static bool _bootstrapped = false;

  @override
  void initState() {
    super.initState();
    if (!_bootstrapped) {
      _bootstrapped = true;
      _bootstrap();
    }
  }

  Future<void> _bootstrap() async {
    double lat, lng;

    if (_demoMode) {
      lat = _newportLat;
      lng = _newportLng;
      if (!mounted) return;
      setState(() => _userLocation = const LatLng(_newportLat, _newportLng));
    } else {
      try {
        LocationPermission perm = await Geolocator.checkPermission();
        if (perm == LocationPermission.denied) {
          perm = await Geolocator.requestPermission();
        }
        final pos = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high,
        );
        lat = pos.latitude;
        lng = pos.longitude;
        if (!mounted) return;
        setState(() => _userLocation = LatLng(lat, lng));
      } catch (_) {
        if (!mounted) return;
        setState(() {
          _loadingResources = false;
          _loadingRisk      = false;
        });
        return;
      }
    }

    await Future.wait([
      _loadResources(lat, lng),
      _loadRisk(lat, lng),
    ]);
  }

  Future<void> _toggleDemoMode() async {
    final next = !_demoMode;
    // Clear all state and cache before switching so modes never mix
    await AppCacheService().clearAll();
    _bootstrapped = false;
    setState(() {
      _demoMode         = next;
      _resourcesData    = null;
      _riskData         = null;
      _userLocation     = null;
      _loadingResources = true;
      _loadingRisk      = true;
      _resourcesError   = '';
    });
    _bootstrap();
  }

  Future<void> _loadResources(double lat, double lng, {bool forceRefresh = false}) async {
    if (!forceRefresh && _resourcesData != null) return;
    if (!mounted) return;
    setState(() { _loadingResources = true; _resourcesError = ''; });

    try {
      final data = await AppCacheService().getOrFetchResources(() async {
        final res = await http.post(
          Uri.parse('http://127.0.0.1:8000/api/resources'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
        ).timeout(const Duration(minutes: 3));
        if (res.statusCode != 200) {
          throw Exception('Status ${res.statusCode}');
        }
        return jsonDecode(res.body) as Map<String, dynamic>;
      });
      if (!mounted) return;
      setState(() { _resourcesData = data; _loadingResources = false; });
    } on TimeoutException {
      if (!mounted) return;
      setState(() {
        _resourcesError   = 'Still analyzing resources — please try again in a moment.';
        _loadingResources = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() { _resourcesError = 'Error: $e'; _loadingResources = false; });
    }
  }

  Future<void> _loadRisk(double lat, double lng) async {
    if (_riskData != null) return;

    try {
      final data = await AppCacheService().getOrFetchRisk(() async {
        final res = await http.post(
          Uri.parse('http://127.0.0.1:8000/api/risk-regions'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
        );
        if (res.statusCode != 200) throw Exception('Status ${res.statusCode}');
        return jsonDecode(res.body) as Map<String, dynamic>;
      });
      if (!mounted) return;
      setState(() { _riskData = data; _loadingRisk = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() => _loadingRisk = false);
      debugPrint('Risk fetch error: $e');
    }
  }

  Future<void> _onRefreshResources() async {
    if (_userLocation == null) return;
    await AppCacheService().clearAll();
    setState(() { _resourcesData = null; _riskData = null; });
    await Future.wait([
      _loadResources(_userLocation!.latitude, _userLocation!.longitude, forceRefresh: true),
      _loadRisk(_userLocation!.latitude, _userLocation!.longitude),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF0C3566),
        foregroundColor: Colors.white,
        title: Text(const ['FloodAid', 'Chat', 'Emergency Resources'][_currentIndex]),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: TextButton.icon(
              onPressed: _toggleDemoMode,
              icon: Icon(
                _demoMode ? Icons.explore : Icons.explore_off,
                color: _demoMode ? Colors.amber : Colors.white54,
                size: 18,
              ),
              label: Text(
                _demoMode ? 'Demo' : 'Live',
                style: TextStyle(
                  color: _demoMode ? Colors.amber : Colors.white54,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: [
          MapScreen(
            userLocation:  _userLocation,
            resourcesData: _resourcesData,
            riskData:      _riskData,
            loading:       _loadingRisk || _loadingResources,
            demoMode:      _demoMode,
          ),
          const ChatScreen(),
          ResourcesScreen(
            resourcesData: _resourcesData,
            loading:       _loadingResources,
            error:         _resourcesError,
            onRefresh:     _onRefreshResources,
          ),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        selectedItemColor: const Color(0xFF1A56DB),
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.map_outlined),
            label: 'Map',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.chat_bubble_outline),
            label: 'Chat',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.health_and_safety_outlined),
            label: 'Resources',
          ),
        ],
      ),
    );
  }
}
