import 'package:flutter/material.dart';

class ResourcesScreen extends StatelessWidget {
  final Map<String, dynamic>? resourcesData;
  final bool loading;
  final String error;
  final Future<void> Function() onRefresh;

  const ResourcesScreen({
    super.key,
    this.resourcesData,
    this.loading = true,
    this.error = '',
    required this.onRefresh,
  });

  // ── Helpers ────────────────────────────────────────────────────────────────

  Map<String, List<dynamic>> get _recommended {
    final rec = resourcesData?['recommended_resources'] ?? {};
    return {
      'hospital': List<dynamic>.from(rec['hospital'] ?? []),
      'shelter': List<dynamic>.from(rec['shelter'] ?? []),
      'food': List<dynamic>.from(rec['food'] ?? []),
    };
  }

  List<dynamic> get _ranked =>
      List<dynamic>.from(resourcesData?['ranked_resources'] ?? []);

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
        return const Color(0xFFE05050);
      case 'food_bank':
      case 'food':
        return const Color(0xFFE8A030);
      case 'shelter':
      case 'evacuation_center':
        return const Color(0xFF1A5FA8);
      default:
        return Colors.grey;
    }
  }

  String _labelForType(String type) {
    switch (type) {
      case 'hospital':
        return 'Hospital';
      case 'urgent_care':
        return 'Urgent Care';
      case 'clinic':
        return 'Clinic';
      case 'food_bank':
      case 'food':
        return 'Food Bank';
      case 'shelter':
      case 'evacuation_center':
        return 'Shelter';
      default:
        return 'Resource';
    }
  }

  // ── Widgets ────────────────────────────────────────────────────────────────

  Widget _resourceCard(Map<String, dynamic> r) {
    final type = r['type'] ?? 'unknown';
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
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
            Text(
              _labelForType(type),
              style: TextStyle(
                color: _colorForType(type),
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            if (r['address'] != null && r['address'].toString().isNotEmpty)
              Text(
                'Address: ${r['address']}',
                style: const TextStyle(fontSize: 12),
              ),
            if (r['phone'] != null && r['phone'].toString().isNotEmpty)
              Text(
                'Phone: ${r['phone']}',
                style: const TextStyle(fontSize: 12),
              ),
            if (r['distance_miles'] != null)
              Text(
                '${r['distance_miles']} miles away',
                style: const TextStyle(fontSize: 12, color: Colors.grey),
              ),
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

  Widget _categorySection(String label, String key) {
    final items = _recommended[key] ?? [];
    if (items.isEmpty) return const SizedBox.shrink();
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
        ...items.map((r) => _resourceCard(Map<String, dynamic>.from(r))),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final hasAny = _recommended.values.any((list) => list.isNotEmpty);

    return Scaffold(
      body: loading
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
          : !hasAny
          ? const Center(child: Text('No resources found nearby'))
          : RefreshIndicator(
              onRefresh: onRefresh,
              child: ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  _categorySection('Hospitals', 'hospital'),
                  _categorySection('Shelters', 'shelter'),
                  _categorySection('Food', 'food'),
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
