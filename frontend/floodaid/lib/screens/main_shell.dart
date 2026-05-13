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

// This is the main screen that holds everything together.
// All the data lives here and gets passed down to the other screens.
class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  // keeps track of which tab we're on (0=Map, 1=Chat, 2=Resources)
  int _currentIndex = 0;

  // demo mode lets us test with Newport, OR instead of needing real GPS
 
  bool _demoMode = false;
  static const _newportLat = 44.6368;
  static const _newportLng = -124.0535;

  // all the data the app needs — fetched once and shared across screens
  LatLng?               _userLocation;    // where the user is , nullable until we get GPS
  Map<String, dynamic>? _resourcesData;  // hospitals, food, shelters
  Map<String, dynamic>? _riskData;       // flood risk zones

  // loading flags so screens can show spinners while we wait
  bool _loadingResources = true;
  bool _loadingRisk      = true;

  // error message if resources fetch breaks
  String _resourcesError = '';

  // this prevents _bootstrap from running twice if flutter rebuilds the widget
  // static means it survives rebuilds but resets on hot restart
  static bool _bootstrapped = false;

  @override
  void initState() {
    super.initState();
    // only run bootstrap once per session
    if (!_bootstrapped) {
      _bootstrapped = true;
      _bootstrap();
    }
  }

  // startup sequence — get location first, then kick off both API calls
  Future<void> _bootstrap() async {
    double lat, lng;

    if (_demoMode) {
      // skip GPS and just use Newport coords
      lat = _newportLat;
      lng = _newportLng;
      if (!mounted) return;
      setState(() => _userLocation = const LatLng(_newportLat, _newportLng));
    } else {
      try {
        // ask for location permission if we don't have it yet
        LocationPermission perm = await Geolocator.checkPermission();
        if (perm == LocationPermission.denied) {
          perm = await Geolocator.requestPermission();
        }

        // get the actual GPS position
        final pos = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high,
        );
        lat = pos.latitude;
        lng = pos.longitude;

        if (!mounted) return;
        setState(() => _userLocation = LatLng(lat, lng));
      } catch (_) {
        // if location completely fails, just stop loading and give up
        if (!mounted) return;
        setState(() {
          _loadingResources = false;
          _loadingRisk      = false;
        });
        return;
      }
    }

    // run both fetches at the same time instead of one after the other
    await Future.wait([
      _loadResources(lat, lng),
      _loadRisk(lat, lng),
    ]);
  }

  // switches between demo and live mode
  // we clear everything first so old data doesn't bleed into the new mode
  Future<void> _toggleDemoMode() async {
    final next = !_demoMode;

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

    // restart the whole bootstrap with the new mode
    _bootstrap();
  }

  // fetches hospitals, food, and shelters from our backend
  // uses the cache so we don't re-fetch every time the widget rebuilds
  Future<void> _loadResources(double lat, double lng, {bool forceRefresh = false}) async {
    if (!forceRefresh && _resourcesData != null) return;
    if (!mounted) return;

    setState(() { _loadingResources = true; _resourcesError = ''; });

    try {
      final data = await AppCacheService().getOrFetchResources(() async {
        // hit our FastAPI backend with the user's location
        final res = await http.post(
          Uri.parse('http://127.0.0.1:8000/api/resources'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
        ).timeout(const Duration(minutes: 3)); // backend AI takes a while

        if (res.statusCode != 200) {
          throw Exception('Status ${res.statusCode}');
        }
        return jsonDecode(res.body) as Map<String, dynamic>;
      });

      if (!mounted) return;
      setState(() { _resourcesData = data; _loadingResources = false; });

    } on TimeoutException {
      // the AI pipeline is slow sometimes, give a helpful message instead of crashing
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

  // fetches the flood risk zones from the backend
  // this triggers the full multi-step AI pipeline on the backend
  Future<void> _loadRisk(double lat, double lng) async {
    if (_riskData != null) return; // already have it, skip

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
      // risk failing isn't fatal — map still works without the circles
      if (!mounted) return;
      setState(() => _loadingRisk = false);
      debugPrint('Risk fetch error: $e');
    }
  }

  // called when user pulls to refresh on the resources screen
  // clears cache and re-fetches everything fresh
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
        // title changes depending on which tab you're on
        title: Text(const ['FloodAid', 'Chat', 'Emergency Resources'][_currentIndex]),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            // demo/live toggle in the top right corner
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

      // IndexedStack keeps all 3 screens mounted at the same time
      // so the map doesn't reload every time you switch tabs
      body: IndexedStack(
        index: _currentIndex,
        children: [
          // tab 0 — the map with risk circles and resource markers
          MapScreen(
            userLocation:  _userLocation,
            resourcesData: _resourcesData,
            riskData:      _riskData,
            loading:       _loadingRisk || _loadingResources,
            demoMode:      _demoMode,
          ),
          // tab 1 — Droppy the chat assistant
          const ChatScreen(),
          // tab 2 — list of nearby resources
          ResourcesScreen(
            resourcesData: _resourcesData,
            loading:       _loadingResources,
            error:         _resourcesError,
            onRefresh:     _onRefreshResources,
          ),
        ],
      ),

      // bottom nav to switch between tabs
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        selectedItemColor:   const Color(0xFF1A56DB),
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