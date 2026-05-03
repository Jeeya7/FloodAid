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

  // Shared app data — fetched once, passed to all screens
  LatLng?               _userLocation;
  Map<String, dynamic>? _resourcesData;
  Map<String, dynamic>? _riskData;
  bool                  _loadingResources = true;
  bool                  _loadingRisk      = true;
  String                _resourcesError   = '';

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    try {
      LocationPermission perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      final pos = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      if (!mounted) return;
      setState(() => _userLocation = LatLng(pos.latitude, pos.longitude));

      // Fire both fetches simultaneously — each checks cache first
      await Future.wait([
        _loadResources(pos.latitude, pos.longitude),
        _loadRisk(pos.latitude, pos.longitude),
      ]);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingResources = false;
        _loadingRisk      = false;
      });
    }
  }

  Future<void> _loadResources(double lat, double lng, {bool forceRefresh = false}) async {
    if (!mounted) return;
    setState(() {
      _loadingResources = true;
      _resourcesError   = '';
    });

    if (!forceRefresh) {
      final cached = await AppCacheService().loadResources();
      if (cached != null) {
        if (!mounted) return;
        setState(() {
          _resourcesData    = cached;
          _loadingResources = false;
        });
        return;
      }
    }

    try {
      final response = await http.post(
        Uri.parse('http://127.0.0.1:8000/api/resources'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
      ).timeout(const Duration(minutes: 3));

      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await AppCacheService().saveResources(data);
        if (!mounted) return;
        setState(() {
          _resourcesData    = data;
          _loadingResources = false;
        });
      } else {
        setState(() {
          _resourcesError   = 'Failed to load resources (${response.statusCode})';
          _loadingResources = false;
        });
      }
    } on TimeoutException {
      if (!mounted) return;
      setState(() {
        _resourcesError   = 'Still analyzing resources — please try again in a moment.';
        _loadingResources = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _resourcesError   = 'Error: $e';
        _loadingResources = false;
      });
    }
  }

  Future<void> _loadRisk(double lat, double lng) async {
    final cached = await AppCacheService().loadRisk();
    if (cached != null) {
      if (!mounted) return;
      setState(() {
        _riskData    = cached;
        _loadingRisk = false;
      });
      return;
    }

    try {
      final response = await http.post(
        Uri.parse('http://127.0.0.1:8000/api/risk-regions'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
      );
      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await AppCacheService().saveRisk(data);
        if (!mounted) return;
        setState(() {
          _riskData    = data;
          _loadingRisk = false;
        });
      } else {
        setState(() => _loadingRisk = false);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _loadingRisk = false);
      debugPrint('Risk API error: $e');
    }
  }

  Future<void> _onRefreshResources() async {
    if (_userLocation == null) return;
    await AppCacheService().clearAll();
    await Future.wait([
      _loadResources(_userLocation!.latitude, _userLocation!.longitude, forceRefresh: true),
      _loadRisk(_userLocation!.latitude, _userLocation!.longitude),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: [
          MapScreen(
            userLocation:  _userLocation,
            resourcesData: _resourcesData,
            riskData:      _riskData,
            loading:       _loadingRisk || _loadingResources,
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
