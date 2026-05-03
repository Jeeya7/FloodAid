import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import '../services/app_cache_service.dart';

class ResourcesScreen extends StatefulWidget {
  const ResourcesScreen({super.key});

  @override
  State<ResourcesScreen> createState() => _ResourcesScreenState();
}

class _ResourcesScreenState extends State<ResourcesScreen> {
  Map<String, List<dynamic>> _recommended = {
    'hospital': [],
    'shelter': [],
    'food': [],
  };
  List<dynamic> _ranked = [];
  bool _loading = true;
  bool _hasFetched = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _fetchResources();
  }

  void _applyData(Map<String, dynamic> data) {
    final rec = data['recommended_resources'] ?? {};
    _recommended = {
      'hospital': List<dynamic>.from(rec['hospital'] ?? []),
      'shelter':  List<dynamic>.from(rec['shelter']  ?? []),
      'food':     List<dynamic>.from(rec['food']     ?? []),
    };
    _ranked  = List<dynamic>.from(data['ranked_resources'] ?? []);
    _loading = false;
  }

  Future<void> _fetchResources({bool forceRefresh = false}) async {
    if (_hasFetched && !forceRefresh) return;
    _hasFetched = true;

    setState(() {
      _loading = true;
      _error = '';
    });

    // Cache hit — no network call needed
    if (!forceRefresh) {
      final cached = await AppCacheService().loadResources();
      if (cached != null) {
        setState(() => _applyData(cached));
        return;
      }
    }

    try {
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      final response = await http.post(
        Uri.parse('http://127.0.0.1:8000/api/resources'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'lat': position.latitude,
          'lng': position.longitude,
          'radius_miles': 25,
        }),
      ).timeout(const Duration(minutes: 3));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await AppCacheService().saveResources(data);
        setState(() => _applyData(data));
      } else {
        setState(() {
          _error   = 'Failed to load resources (${response.statusCode})';
          _loading = false;
        });
      }
    } on TimeoutException {
      setState(() {
        _error      = 'Still analyzing resources — please try again in a moment.';
        _loading    = false;
        _hasFetched = false;
      });
    } catch (e) {
      setState(() {
        _error      = 'Error: $e';
        _loading    = false;
        _hasFetched = false;
      });
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

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
      case 'hospital':    return 'Hospital';
      case 'urgent_care': return 'Urgent Care';
      case 'clinic':      return 'Clinic';
      case 'food_bank':
      case 'food':        return 'Food Bank';
      case 'shelter':
      case 'evacuation_center': return 'Shelter';
      default:            return 'Resource';
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
              Text(r['address'], style: const TextStyle(fontSize: 12)),
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
        trailing: r['phone'] != null && r['phone'].toString().isNotEmpty
            ? IconButton(
                icon: const Icon(Icons.phone, color: Color(0xFF1A5FA8)),
                onPressed: () {},
              )
            : null,
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
      appBar: AppBar(
        title: const Text('Emergency Resources'),
        backgroundColor: const Color(0xFF0C3566),
        foregroundColor: Colors.white,
      ),
      body: _loading
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
          : _error.isNotEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(_error, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: () => _fetchResources(forceRefresh: true),
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : !hasAny
                  ? const Center(child: Text('No resources found nearby'))
                  : RefreshIndicator(
                      onRefresh: () => _fetchResources(forceRefresh: true),
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