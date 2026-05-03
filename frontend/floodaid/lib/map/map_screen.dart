import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final MapController _mapController = MapController();
  LatLng? _userLocation;
  bool _loading = true;

  // Risk
  String _riskLevel = 'low'; // 'high', 'moderate', 'low'

  // Resource markers
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

      // Call both APIs
      await Future.wait([
        _fetchRisk(position.latitude, position.longitude),
        _fetchResources(position.latitude, position.longitude),
      ]);

    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _fetchRisk(double lat, double lng) async {
    try {
      final response = await http.post(
        Uri.parse('http://localhost:8000/api/risk-regions'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final score = data['risk_score'] ?? 0;
        setState(() {
          if (score >= 70) {
            _riskLevel = 'high';
          } else if (score >= 40) {
            _riskLevel = 'moderate';
          } else {
            _riskLevel = 'low';
          }
        });
      }
    } catch (e) {
      print('Risk API error: $e');
    }
  }

  Future<void> _fetchResources(double lat, double lng) async {
    try {
      final response = await http.post(
        Uri.parse('http://localhost:8000/api/resources'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'lat': lat, 'lng': lng, 'radius_miles': 25}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final List resources = data['resources'] ?? [];
        setState(() {
          _resourceMarkers = resources.map<Marker>((r) {
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
        });
      }
    } catch (e) {
      print('Resources API error: $e');
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
              // Resource markers
              if (_resourceMarkers.isNotEmpty)
                MarkerLayer(markers: _resourceMarkers),
              // User location
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

          // Risk banner at top
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

          // Loading spinner
          if (_loading)
            const Center(child: CircularProgressIndicator()),

          // Re-center button
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

          // Legend
          Positioned(
            bottom: 90,
            right: 16,
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(10),
                boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.1), blurRadius: 6)],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _legendItem(Icons.local_hospital, Colors.red, 'Hospital'),
                  _legendItem(Icons.fastfood, Colors.orange, 'Food Bank'),
                  _legendItem(Icons.home, Colors.blue, 'Shelter'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _legendItem(IconData icon, Color color, String label) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Icon(icon, color: color, size: 16),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(fontSize: 11)),
        ],
      ),
    );
  }
}