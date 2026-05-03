import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import '../services/app_cache_service.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final MapController _mapController = MapController();
  LatLng? _userLocation;
  bool _loading = true;
  String _riskLevel = 'low';
  List<Marker> _resourceMarkers = [];

  @override
  void initState() {
    super.initState();
    _getLocation();
  }

  Future<void> _getLocation() async {
    try {
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      setState(() {
        _userLocation = LatLng(position.latitude, position.longitude);
        _loading = false;
      });

      _mapController.move(_userLocation!, 12.0);

      await Future.wait([
        _fetchRisk(position.latitude, position.longitude),
        _fetchResources(position.latitude, position.longitude),
      ]);

    } catch (e) {
      setState(() => _loading = false);
    }
  }

  void _applyRiskScore(int score) {
    if (score >= 70) {
      _riskLevel = 'high';
    } else if (score >= 40) {
      _riskLevel = 'moderate';
    } else {
      _riskLevel = 'low';
    }
  }

  List<Marker> _buildMarkers(List resources) {
    return resources.map<Marker>((r) {
      final type = r['type'] ?? 'shelter';
      return Marker(
        point: LatLng(
          (r['lat'] as num).toDouble(),
          (r['lng'] as num).toDouble(),
        ),
        width: 36,
        height: 36,
        child: Tooltip(
          message: r['name'] ?? type,
          child: Icon(
            _iconForType(type),
            color: _colorForType(type),
            size: 30,
          ),
        ),
      );
    }).toList();
  }

  Future<void> _fetchRisk(double lat, double lng) async {
    // Cache hit
    final cached = await AppCacheService().loadRisk();
    if (cached != null) {
      setState(() => _applyRiskScore((cached['risk_score'] as num?)?.toInt() ?? 0));
      return;
    }

    try {
      final response = await http.post(
        Uri.parse('http://localhost:8000/api/risk-regions'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await AppCacheService().saveRisk(data);
        setState(() => _applyRiskScore((data['risk_score'] as num?)?.toInt() ?? 0));
      }
    } catch (e) {
      debugPrint('Risk API error: $e');
    }
  }

  Future<void> _fetchResources(double lat, double lng) async {
    // Cache hit — ranked_resources is the flat list used for map markers
    final cached = await AppCacheService().loadResources();
    if (cached != null) {
      final List resources = cached['ranked_resources'] ?? [];
      setState(() => _resourceMarkers = _buildMarkers(resources));
      return;
    }

    try {
      final response = await http.post(
        Uri.parse('http://localhost:8000/api/resources'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await AppCacheService().saveResources(data);
        final List resources = data['ranked_resources'] ?? [];
        setState(() => _resourceMarkers = _buildMarkers(resources));
      }
    } catch (e) {
      debugPrint('Resources API error: $e');
    }
  }

  IconData _iconForType(String type) {
    switch (type) {
      case 'hospital':
      case 'urgent_care':
      case 'clinic':
        return Icons.local_hospital;
      case 'food_bank':
      case 'food':
        return Icons.fastfood;
      case 'shelter':
      case 'evacuation_center':
        return Icons.home;
      default:
        return Icons.place;
    }
  }

  Color _colorForType(String type) {
    switch (type) {
      case 'hospital':
      case 'urgent_care':
      case 'clinic':
        return Colors.red;
      case 'food_bank':
      case 'food':
        return Colors.orange;
      case 'shelter':
      case 'evacuation_center':
        return Colors.blue;
      default:
        return Colors.grey;
    }
  }

  Color _riskColor() {
    switch (_riskLevel) {
      case 'high':
        return const Color(0xFFE05050);
      case 'moderate':
        return const Color(0xFFE8A030);
      default:
        return const Color(0xFF4AAD6A);
    }
  }

  String _riskLabel() {
    switch (_riskLevel) {
      case 'high':
        return 'HIGH FLOOD RISK';
      case 'moderate':
        return 'MODERATE FLOOD RISK';
      default:
        return 'LOW FLOOD RISK — Area appears safe';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FloodAid'),
        backgroundColor: const Color(0xFF0C3566),
        foregroundColor: Colors.white,
      ),
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: const LatLng(37.5, -96.0),
              initialZoom: 4.5,
              minZoom: 4.5,
              cameraConstraint: CameraConstraint.containCenter(
                bounds: LatLngBounds(
                  const LatLng(25.84, -124.67),
                  const LatLng(49.38, -66.93),
                ),
              ),
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.floodaid.app',
              ),
              if (_resourceMarkers.isNotEmpty)
                MarkerLayer(markers: _resourceMarkers),
              if (_userLocation != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: _userLocation!,
                      width: 40,
                      height: 40,
                      child: const Icon(
                        Icons.my_location,
                        color: Colors.blue,
                        size: 36,
                      ),
                    ),
                  ],
                ),
            ],
          ),

          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: Container(
              color: _riskColor(),
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
              child: Text(
                _riskLabel(),
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          ),

          if (_loading)
            const Center(child: CircularProgressIndicator()),

          Positioned(
            bottom: 20,
            right: 16,
            child: FloatingActionButton(
              backgroundColor: const Color(0xFF1A5FA8),
              onPressed: () {
                if (_userLocation != null) {
                  _mapController.move(_userLocation!, 12.0);
                }
              },
              child: const Icon(Icons.my_location, color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }
}