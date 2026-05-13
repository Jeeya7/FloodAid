import 'package:flutter/material.dart';

// ResourcesScreen shows a list view of all nearby hospitals, food, and shelters
// it gets its data passed in from MainShell — it doesn't fetch anything itself
class ResourcesScreen extends StatelessWidget {
  final Map<String, dynamic>? resourcesData; // the full response from /api/resources
  final bool loading;                         // shows spinner while data loads
  final String error;                         // shows error message if fetch failed
  final Future<void> Function() onRefresh;   // called when user pulls to refresh

  const ResourcesScreen({
    super.key,
    this.resourcesData,
    this.loading = true,
    this.error = '',
    required this.onRefresh,
  });

  // ── Helpers ────────────────────────────────────────────────────────────────

  // pulls out the recommended resources split by category
  // returns a map so we can easily grab hospitals, shelters, food separately
  Map<String, List<dynamic>> get _recommended {
    final rec = resourcesData?['recommended_resources'] ?? {};
    return {
      'hospital': List<dynamic>.from(rec['hospital'] ?? []),
      'shelter':  List<dynamic>.from(rec['shelter']  ?? []),
      'food':     List<dynamic>.from(rec['food']     ?? []),
    };
  }

  // the ranked list — all resources sorted by relevance/distance
  // shown at the bottom under "All Resources"
  List<dynamic> get _ranked =>
      List<dynamic>.from(resourcesData?['ranked_resources'] ?? []);

  // picks the right icon based on resource type
  // same logic as map_screen.dart so they stay consistent
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
        return const Color(0xFFE05050); // red
      case 'food_bank':
      case 'food':
        return const Color(0xFFE8A030); // orange
      case 'shelter':
      case 'evacuation_center':
        return const Color(0xFF1A5FA8); // blue
      default:
        return Colors.grey;
    }
  }

  // human readable label for each resource type
  String _labelForType(String type) {
    switch (type) {
      case 'hospital':        return 'Hospital';
      case 'urgent_care':     return 'Urgent Care';
      case 'clinic':          return 'Clinic';
      case 'food_bank':
      case 'food':            return 'Food Bank';
      case 'shelter':
      case 'evacuation_center': return 'Shelter';
      default:                return 'Resource';
    }
  }

  // ── Widgets ────────────────────────────────────────────────────────────────

  // single resource card showing name, type, address, phone, distance
  Widget _resourceCard(Map<String, dynamic> r) {
    final type = r['type'] ?? 'unknown';
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        // colored circle with icon on the left
        leading: CircleAvatar(
          backgroundColor: _colorForType(type).withOpacity(0.15),
          child: Icon(_iconForType(type), color: _colorForType(type)),
        ),
        title: Text(
          r['name'] ?? 'Unknown',
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 2),
            // colored type label e.g. "Hospital" in red
            Text(
              _labelForType(type),
              style: TextStyle(
                color: _colorForType(type),
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            // only show address if we have one
            if (r['address'] != null && r['address'].toString().isNotEmpty)
              Text(
                'Address: ${r['address']}',
                style: const TextStyle(fontSize: 12),
              ),
            // only show phone if we have one
            if (r['phone'] != null && r['phone'].toString().isNotEmpty)
              Text(
                'Phone: ${r['phone']}',
                style: const TextStyle(fontSize: 12),
              ),
            // distance from user's location
            if (r['distance_miles'] != null)
              Text(
                '${r['distance_miles']} miles away',
                style: const TextStyle(fontSize: 12, color: Colors.grey),
              ),
            // AI reasoning for why this resource was recommended
            if (r['reasoning'] != null && r['reasoning'].toString().isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  r['reasoning'],
                  style: const TextStyle(fontSize: 11, color: Colors.grey),
                ),
              ),
          ],
        ),
      ),
    );
  }

  // a section with a header and a list of cards for one category
  // e.g. "Hospitals" with all the hospital cards below it
  Widget _categorySection(String label, String key) {
    final items = _recommended[key] ?? [];
    if (items.isEmpty) return const SizedBox.shrink(); // hide if no items
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 16, 4, 6),
          child: Text(
            label,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: Color(0xFF0C3566),
            ),
          ),
        ),
        // render a card for each resource in this category
        ...items.map((r) => _resourceCard(Map<String, dynamic>.from(r))),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    // check if we have any resources at all across all categories
    final hasAny = _recommended.values.any((list) => list.isNotEmpty);

    return Scaffold(
      body: loading
          // still waiting for backend — show spinner
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Text(
                    'Analyzing nearby resources…',
                    style: TextStyle(color: Colors.grey),
                  ),
                ],
              ),
            )
          // something went wrong — show error and retry button
          : error.isNotEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(error, textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: onRefresh,
                    child: const Text('Retry'),
                  ),
                ],
              ),
            )
          // loaded but nothing nearby
          : !hasAny
          ? const Center(child: Text('No resources found nearby'))
          // we have data — show the full list with pull to refresh
          : RefreshIndicator(
              onRefresh: onRefresh,
              child: ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  // recommended resources split by category
                  _categorySection('Hospitals', 'hospital'),
                  _categorySection('Shelters', 'shelter'),
                  _categorySection('Food',     'food'),
                  // ranked list at the bottom showing everything together
                  if (_ranked.isNotEmpty) ...[
                    const Padding(
                      padding: EdgeInsets.fromLTRB(4, 24, 4, 6),
                      child: Text(
                        'All Resources',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF0C3566),
                        ),
                      ),
                    ),
                    ..._ranked.map(
                      (r) => _resourceCard(Map<String, dynamic>.from(r)),
                    ),
                  ],
                ],
              ),
            ),
    );
  }
}