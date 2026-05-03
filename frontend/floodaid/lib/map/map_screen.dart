import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

class MapScreen extends StatefulWidget {
  final LatLng?               userLocation;
  final Map<String, dynamic>? resourcesData;
  final Map<String, dynamic>? riskData;
  final bool                  loading;
  final bool                  demoMode;

  const MapScreen({
    super.key,
    this.userLocation,
    this.resourcesData,
    this.riskData,
    this.loading  = true,
    this.demoMode = false,
  });

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final MapController _mapController = MapController();
  bool _movedToUser = false;

  @override
  void didUpdateWidget(MapScreen old) {
    super.didUpdateWidget(old);
    if (!_movedToUser && widget.userLocation != null) {
      _movedToUser = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _mapController.move(widget.userLocation!, 12.0);
      });
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  String _riskLevel() {
    final score = (widget.riskData?['risk_score'] as num?)?.toInt() ?? 0;
    if (score >= 70) return 'high';
    if (score >= 40) return 'moderate';
    return 'low';
  }

  Color _riskColor() {
    switch (_riskLevel()) {
      case 'high':     return const Color(0xFFE05050);
      case 'moderate': return const Color(0xFFE8A030);
      default:         return const Color(0xFF4AAD6A);
    }
  }

  String _riskLabel() {
    switch (_riskLevel()) {
      case 'high':     return 'HIGH FLOOD RISK';
      case 'moderate': return 'MODERATE FLOOD RISK';
      default:         return 'LOW FLOOD RISK — Area appears safe';
    }
  }

  List<Marker> _buildResourceMarkers() {
    final List resources = widget.resourcesData?['ranked_resources'] ?? [];
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
          child: Icon(_iconForType(type), color: _colorForType(type), size: 30),
        ),
      );
    }).toList();
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

  @override
  Widget build(BuildContext context) {
    final markers = _buildResourceMarkers();

    return Scaffold(
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
              if (markers.isNotEmpty)
                MarkerLayer(markers: markers),
              if (widget.userLocation != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: widget.userLocation!,
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

          if (widget.loading)
            const Center(child: CircularProgressIndicator()),

          Positioned(
            bottom: 20,
            right: 16,
            child: FloatingActionButton(
              backgroundColor: const Color(0xFF1A5FA8),
              onPressed: () {
                if (widget.userLocation != null) {
                  _mapController.move(widget.userLocation!, 12.0);
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
