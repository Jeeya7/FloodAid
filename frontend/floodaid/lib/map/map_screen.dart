import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

class MapScreen extends StatelessWidget {
  const MapScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FloodAid'),
        backgroundColor: const Color(0xFF0C3566),
        foregroundColor: Colors.white,
      ),
      body: FlutterMap(
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
        ],
      ),
    );
  }
}