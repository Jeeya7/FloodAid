import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

// MapScreen receives all its data from MainShell — it doesn't fetch anything itself
// it just takes the data and draws it on the map
class MapScreen extends StatefulWidget {
  final LatLng?               userLocation;   // where the user is
  final Map<String, dynamic>? resourcesData;  // hospitals, food, shelters
  final Map<String, dynamic>? riskData;       // flood risk regions
  final bool                  loading;        // shows spinner while data is loading
  final bool                  demoMode;       // true if using Newport coords instead of GPS

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
  // lets us move the map camera programmatically
  final MapController _mapController = MapController();

  // tracks whether we've already zoomed to the user's location
  // so we don't keep snapping back every time the widget rebuilds
  bool _movedToUser = false;

  @override
  void initState() {
    super.initState();
    // if location is already available when the map first loads, zoom to it immediately
    if (widget.userLocation != null) {
      _movedToUser = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _mapController.move(widget.userLocation!, 12.0);
      });
    }
  }

  @override
  void didUpdateWidget(MapScreen old) {
    super.didUpdateWidget(old);
    // if location wasn't ready on first load but arrives later, zoom to it now
    // only do this once — hence the _movedToUser flag
    if (!_movedToUser && widget.userLocation != null) {
      _movedToUser = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _mapController.move(widget.userLocation!, 12.0);
      });
    }
  }

  // ── Risk helpers ──────────────────────────────────────────────────────────

  // looks through all risk regions and returns the worst one
  // so we can show the right color on the banner at the top
  String _overallRiskLevel() {
    final regions = (widget.riskData?['regions'] as List?) ?? [];
    if (regions.isEmpty) return 'low';
    const order = ['low', 'moderate', 'high', 'critical'];
    String worst = 'low';
    for (final r in regions) {
      final level = (r['risk_level'] ?? 'low') as String;
      if (order.indexOf(level) > order.indexOf(worst)) {
        worst = level;
      }
    }
    return worst;
  }

  // maps risk level string to a color for the circles and banner
  Color _colorForRiskLevel(String level) {
    switch (level) {
      case 'critical': return const Color(0xFFDC2626); // red
      case 'high':     return const Color(0xFFE05050); // light red
      case 'moderate': return const Color(0xFFE8A030); // orange
      default:         return const Color(0xFF4AAD6A); // green
    }
  }

  // maps risk level to a human readable message for the banner
  String _labelForRiskLevel(String level) {
    switch (level) {
      case 'critical': return 'CRITICAL FLOOD RISK — Evacuate immediately';
      case 'high':     return 'HIGH FLOOD RISK — Take action now';
      case 'moderate': return 'MODERATE FLOOD RISK — Stay alert';
      default:         return 'LOW FLOOD RISK — Area appears safe';
    }
  }

  // ── Region circle markers ─────────────────────────────────────────────────

  // builds the colored circles on the map showing flood risk zones
  // each circle is 18km radius around a USGS gauge station
  List<CircleMarker> _buildRiskCircles() {
    final regions = (widget.riskData?['regions'] as List?) ?? [];
    return regions.map<CircleMarker?>((r) {
      final level = (r['risk_level'] ?? 'low') as String;
      final lat = (r['center']?['lat'] as num?)?.toDouble();
      final lng = (r['center']?['lng'] as num?)?.toDouble();
      if (lat == null || lng == null) return null; // skip if no coordinates
      final color = _colorForRiskLevel(level);
      return CircleMarker(
        point: LatLng(lat, lng),
        radius: 18000,              // 18km radius
        useRadiusInMeter: true,     // radius is in meters not pixels
        color: color.withOpacity(0.25),     // transparent fill
        borderColor: color.withOpacity(0.8), // solid-ish border
        borderStrokeWidth: 2,
      );
    }).whereType<CircleMarker>().toList(); // filter out the nulls
  }

  // ── Region label markers ──────────────────────────────────────────────────

  // builds the little text labels that sit on top of each risk circle
  // shows the risk level and region name
  List<Marker> _buildRiskLabelMarkers() {
    final regions = (widget.riskData?['regions'] as List?) ?? [];
    return regions.map<Marker?>((r) {
      final level = (r['risk_level'] ?? 'low') as String;
      final lat = (r['center']?['lat'] as num?)?.toDouble();
      final lng = (r['center']?['lng'] as num?)?.toDouble();
      final name = (r['name'] ?? '') as String;
      if (lat == null || lng == null) return null;
      final color = _colorForRiskLevel(level);
      return Marker(
        point: LatLng(lat, lng),
        width: 120,
        height: 48,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // colored pill showing risk level e.g. "HIGH"
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              decoration: BoxDecoration(
                color: color.withOpacity(0.9),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                level.toUpperCase(),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(height: 2),
            // white pill showing region name, truncated if too long
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.85),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                name.length > 20 ? '${name.substring(0, 20)}...' : name,
                style: const TextStyle(fontSize: 8, color: Color(0xFF1F2937)),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      );
    }).whereType<Marker>().toList();
  }

  // ── Resource markers ──────────────────────────────────────────────────────

  // builds all the hospital/food/shelter icons on the map
  // merges recommended_resources and ranked_resources to avoid duplicates
  List<Marker> _buildResourceMarkers() {
    final rec = widget.resourcesData?['recommended_resources'] ?? {};

    // step 1 — collect all resources from recommended_resources
    // use a map keyed by id so we can easily merge without duplicates
    final Map<String, Map<String, dynamic>> allById = {};
    for (final category in ['hospital', 'shelter', 'food']) {
      final list = rec[category] as List? ?? [];
      for (final r in list) {
        final item = Map<String, dynamic>.from(r as Map);
        item['type'] ??= category; // make sure type is set for icon selection
        final id = item['id'] as String?;
        if (id != null) {
          allById[id] = item;
        } else {
          // no id — give it a unique key so it still shows up
          allById['__${category}_${allById.length}'] = item;
        }
      }
    }

    // step 2 — merge ranked_resources on top
    // ranked might have better/updated coordinates so we prefer those
    final ranked = widget.resourcesData?['ranked_resources'] as List? ?? [];
    for (final r in ranked) {
      final item = Map<String, dynamic>.from(r as Map);
      item['type'] ??= 'unknown';
      final id = item['id'] as String?;
      if (id != null && allById.containsKey(id)) {
        // already have this one — update coords if ranked has valid ones
        final rLat = (item['lat'] as num?)?.toDouble() ?? 0;
        final rLng = (item['lng'] as num?)?.toDouble() ?? 0;
        if (rLat != 0 && rLng != 0) {
          allById[id]!['lat'] = rLat;
          allById[id]!['lng'] = rLng;
        }
      } else {
        // new resource not in recommended — add it
        allById[id ?? '__ranked_${allById.length}'] = item;
      }
    }

    // step 3 — turn each resource into a map marker
    return allById.values.map<Marker?>((r) {
      final type = (r['type'] ?? 'unknown') as String;
      final lat  = (r['lat'] as num?)?.toDouble();
      final lng  = (r['lng'] as num?)?.toDouble();

      // skip anything with missing or zero coordinates
      if (lat == null || lng == null || (lat == 0 && lng == 0)) return null;

      return Marker(
        point: LatLng(lat, lng),
        width: 36,
        height: 36,
        child: Tooltip(
          message: (r['name'] ?? type) as String, // shows name on long press
          child: Icon(_iconForType(type), color: _colorForType(type), size: 30),
        ),
      );
    }).whereType<Marker>().toList();
  }

  // picks the right icon based on resource type
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

  // picks the right color based on resource type
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

  // ── Legend ────────────────────────────────────────────────────────────────

  // the little legend box in the bottom left corner
  // explains what all the colors and icons mean
  Widget _buildLegend() {
    return Positioned(
      bottom: 80,
      left: 16,
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.92),
          borderRadius: BorderRadius.circular(10),
          boxShadow: const [BoxShadow(color: Colors.black12, blurRadius: 6)],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Flood Risk', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            _legendRow(const Color(0xFFDC2626), 'Critical'),
            _legendRow(const Color(0xFFE05050), 'High'),
            _legendRow(const Color(0xFFE8A030), 'Moderate'),
            _legendRow(const Color(0xFF4AAD6A), 'Low'),
            const SizedBox(height: 6),
            const Text('Resources', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            _legendIcon(Icons.local_hospital, Colors.red,    'Hospital'),
            _legendIcon(Icons.fastfood,       Colors.orange, 'Food'),
            _legendIcon(Icons.home,           Colors.blue,   'Shelter'),
          ],
        ),
      ),
    );
  }

  // single row in the legend with a colored dot and a label
  Widget _legendRow(Color color, String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 3),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(fontSize: 10)),
        ],
      ),
    );
  }

  // single row in the legend with an icon and a label
  Widget _legendIcon(IconData icon, Color color, String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 3),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 14),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(fontSize: 10)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // build all the layers before passing them to the map
    final riskLevel       = _overallRiskLevel();
    final riskCircles     = _buildRiskCircles();
    final riskLabels      = _buildRiskLabelMarkers();
    final resourceMarkers = _buildResourceMarkers();

    return Scaffold(
      body: Stack(
        children: [
          // the base map — everything else is layered on top
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              // if we have the user's location use it, otherwise show the whole US
              initialCenter: widget.userLocation ?? const LatLng(37.5, -96.0),
              initialZoom: widget.userLocation != null ? 12.0 : 4.5,
              minZoom: 4.5,
              // lock the map so you can't pan outside the US
              cameraConstraint: CameraConstraint.containCenter(
                bounds: LatLngBounds(
                  const LatLng(25.84, -124.67), // bottom left (SW corner of US)
                  const LatLng(49.38, -66.93),  // top right (NE corner of US)
                ),
              ),
            ),
            children: [
              // base map tiles from OpenStreetMap
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.floodaid.app',
              ),
              // flood risk circles — only render if we have data
              if (riskCircles.isNotEmpty)
                CircleLayer(circles: riskCircles),
              // risk level text labels on top of the circles
              if (riskLabels.isNotEmpty)
                MarkerLayer(markers: riskLabels),
              // hospital/food/shelter icons
              if (resourceMarkers.isNotEmpty)
                MarkerLayer(markers: resourceMarkers),
              // blue dot showing where the user is
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
          // colored banner at the top showing overall risk level
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: Container(
              color: _colorForRiskLevel(riskLevel),
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
              child: Text(
                _labelForRiskLevel(riskLevel),
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          ),
          // spinner shown while data is still loading
          if (widget.loading)
            const Center(child: CircularProgressIndicator()),
          // legend box in the bottom left
          _buildLegend(),
          // button in the bottom right to re-center on user's location
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
