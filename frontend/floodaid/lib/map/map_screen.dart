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

  @override
  void initState() {
    super.initState();
    _getLocation();
  }

  Future<void> _callBackend(double lat, double lng) async {
    try {
      final response = await http.post(
        Uri.parse('http://localhost:8000/resources'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'latitude': lat, 'longitude': lng}),
      );
      print('Backend: ${response.body}');
    } catch (e) {
      print('Backend error: $e');
    }
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

      // Send coordinates to backend
      await _callBackend(position.latitude, position.longitude);

    } catch (e) {
      setState(() => _loading = false);
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