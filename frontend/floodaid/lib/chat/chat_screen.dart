import 'dart:async';
import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_svg/flutter_svg.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  // controls the text input field at the bottom
  final TextEditingController _controller = TextEditingController();
  // lets us scroll the message list to the bottom when a new message arrives
  final ScrollController _scrollController = ScrollController();

  // true while waiting for Droppy's response — shows the typing dots
  bool _isTyping = false;

  // alert banner at the top — defaults to yellow/moderate while loading
  String _alertText = 'Checking flood status...';
  Color _alertColor = const Color(0xFFFEF3C7);
  Color _alertTextColor = const Color(0xFF92400E);
  Color _alertIconColor = const Color(0xFFD97706);

  // the actual chat messages shown on screen
  // starts with Droppy's welcome message
  final List<Map<String, String>> _messages = [
    {
      'role': 'bot',
      'text': "You're safe, I'm here to help ♥\n\nI'm Droppy, your FloodAid assistant. I can help you find the nearest shelter, food, medical help, or your evacuation route.\n\nWhat do you need right now?",
    },
  ];

  // conversation history we send to the backend so Droppy remembers context
  // this is separate from _messages because it uses a different format
  final List<Map<String, String>> _history = [];

  // quick reply chips shown above the text input
  final List<String> _suggestions = [
    'Am I in danger?',
    'Where is the nearest shelter?',
    'Is there food nearby?',
    'Who can I call?',
  ];

  static const String _backendUrl = 'http://127.0.0.1:8000';

  @override
  void initState() {
    super.initState();
    // fetch the current flood alert as soon as the screen loads
    _fetchAlert();
  }

  // hits /api/alert to get the current worst flood risk level
  // then updates the banner color to match (green/yellow/orange/red)
  Future<void> _fetchAlert() async {
    try {
      final response = await http
          .get(Uri.parse('$_backendUrl/api/alert'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final riskLevel = data['risk_level'] ?? 'low';
        final alertText = data['alert'] ?? 'No active flood alerts';

        setState(() {
          _alertText = alertText;
          // change banner colors based on risk level
          switch (riskLevel) {
            case 'critical':
              _alertColor = const Color(0xFFFFE4E4);      // red background
              _alertTextColor = const Color(0xFF991B1B);
              _alertIconColor = const Color(0xFFDC2626);
              break;
            case 'high':
              _alertColor = const Color(0xFFFFEDD5);      // orange background
              _alertTextColor = const Color(0xFF9A3412);
              _alertIconColor = const Color(0xFFEA580C);
              break;
            case 'moderate':
              _alertColor = const Color(0xFFFEF3C7);      // yellow background
              _alertTextColor = const Color(0xFF92400E);
              _alertIconColor = const Color(0xFFD97706);
              break;
            default:
              _alertColor = const Color(0xFFDCFCE7);      // green background
              _alertTextColor = const Color(0xFF166534);
              _alertIconColor = const Color(0xFF16A34A);
          }
        });
      }
    } catch (_) {
      // if the alert fetch fails just show a neutral message, not a crash
      setState(() {
        _alertText = 'Could not load flood status';
      });
    }
  }

  // called when the user sends a message (via button, enter key, or suggestion chip)
  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty) return; // ignore empty messages

    setState(() {
      _messages.add({'role': 'user', 'text': text});       // show user message
      _history.add({'role': 'user', 'content': text});     // add to history for backend
      _isTyping = true;                                     // show typing dots
    });

    _controller.clear();
    _scrollToBottom();

    try {
      // send the message + full history to the backend
      // history lets Droppy remember what was said earlier in the conversation
      final response = await http.post(
        Uri.parse('$_backendUrl/api/chat'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'message': text, 'history': _history}),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final reply = data['response'] ?? 'Sorry, I did not get that. Please try again.';

        setState(() {
          _messages.add({'role': 'bot', 'text': reply});           // show Droppy's reply
          _history.add({'role': 'assistant', 'content': reply});   // add to history
          _isTyping = false;                                        // hide typing dots
        });
      } else {
        _showError();
      }
    } catch (e) {
      _showError();
    }

    _scrollToBottom();
  }

  // shows a friendly error message if the backend call fails
  void _showError() {
    setState(() {
      _messages.add({
        'role': 'bot',
        'text': 'I am having trouble connecting right now. Please check your connection and try again.',
      });
      _isTyping = false;
    });
  }

  // scrolls the chat list to the bottom so the latest message is always visible
  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // clean up controllers when the screen is removed from memory
  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF9FAFB),
      appBar: _buildAppBar(),
      body: Column(
        children: [
          _buildAlertBanner(),           // flood status banner at top
          Expanded(child: _buildMessageList()),  // scrollable chat messages
          if (_isTyping) _buildTypingIndicator(), // animated dots while waiting
          _buildSuggestions(),           // quick reply chips
          _buildComposer(),              // text input + send button
        ],
      ),
    );
  }

  // the top bar showing Droppy's name and online status
  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: Colors.white,
      elevation: 0.5,
      leading: Padding(
        padding: const EdgeInsets.all(6.0),
        child: ClipOval(
          child: SvgPicture.asset(
            'assets/floodaid_logo.svg',
            width: 40,
            height: 40,
            fit: BoxFit.cover,
          ),
        ),
      ),
      title: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Droppy',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Color(0xFF1A56DB),
            ),
          ),
          Row(
            children: [
              // green dot to show Droppy is online
              CircleAvatar(radius: 4, backgroundColor: Color(0xFF16A34A)),
              SizedBox(width: 4),
              Text(
                'Emergency Support • Online',
                style: TextStyle(fontSize: 12, color: Color(0xFF16A34A)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // colored banner at the top showing current flood alert
  Widget _buildAlertBanner() {
    return Container(
      width: double.infinity,
      color: _alertColor,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Icon(Icons.warning_amber_rounded, color: _alertIconColor, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _alertText,
              style: TextStyle(
                fontSize: 13,
                color: _alertTextColor,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // scrollable list of chat bubbles
  Widget _buildMessageList() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      itemCount: _messages.length,
      itemBuilder: (context, index) {
        final msg = _messages[index];
        final isBot = msg['role'] == 'bot';
        return _buildBubble(msg['text'] ?? '', isBot);
      },
    );
  }

  // single chat bubble — blue on the right for user, white on the left for Droppy
  Widget _buildBubble(String text, bool isBot) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment: isBot ? MainAxisAlignment.start : MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          // show Droppy's logo next to bot messages
          if (isBot) ...[
            ClipOval(
              child: SvgPicture.asset(
                'assets/floodaid_logo.svg',
                width: 28,
                height: 28,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isBot ? Colors.white : const Color(0xFF1A56DB),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  // the pointy corner shows which side the message is on
                  bottomLeft: Radius.circular(isBot ? 4 : 16),
                  bottomRight: Radius.circular(isBot ? 16 : 4),
                ),
                border: isBot
                    ? Border.all(color: const Color(0xFFE5E7EB), width: 0.5)
                    : null,
              ),
              child: Text(
                text,
                style: TextStyle(
                  fontSize: 14,
                  height: 1.5,
                  color: isBot ? const Color(0xFF111827) : Colors.white,
                ),
              ),
            ),
          ),
          if (!isBot) const SizedBox(width: 8),
        ],
      ),
    );
  }

  // animated dots that show while waiting for Droppy's response
  Widget _buildTypingIndicator() {
    return Padding(
      padding: const EdgeInsets.only(left: 16, bottom: 8),
      child: Row(
        children: [
          ClipOval(
            child: SvgPicture.asset(
              'assets/floodaid_logo.svg',
              width: 28,
              height: 28,
              fit: BoxFit.cover,
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE5E7EB), width: 0.5),
            ),
            // 3 dots with staggered animation
            child: Row(children: List.generate(3, (i) => _buildDot(i))),
          ),
        ],
      ),
    );
  }

  // single animated dot — each one is slightly delayed so they pulse one after another
  Widget _buildDot(int index) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 600 + (index * 200)), // staggered delay
      builder: (context, value, child) {
        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 2),
          width: 7,
          height: 7,
          decoration: BoxDecoration(
            // color animates from grey to blue
            color: Color.lerp(
              const Color(0xFFD1D5DB),
              const Color(0xFF1A56DB),
              value,
            ),
            shape: BoxShape.circle,
          ),
        );
      },
    );
  }

  // horizontal scrollable row of quick reply suggestion chips
  Widget _buildSuggestions() {
    return SizedBox(
      height: 40,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: _suggestions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          return GestureDetector(
            // tapping a suggestion sends it as a message
            onTap: () => _sendMessage(_suggestions[index]),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(99),
                border: Border.all(color: const Color(0xFFE5E7EB)),
              ),
              child: Text(
                _suggestions[index],
                style: const TextStyle(fontSize: 12, color: Color(0xFF374151)),
              ),
            ),
          );
        },
      ),
    );
  }

  // text input field and send button at the bottom
  Widget _buildComposer() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      color: Colors.white,
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              onSubmitted: _sendMessage, // send on enter key
              decoration: InputDecoration(
                hintText: 'Type a message...',
                hintStyle: const TextStyle(color: Color(0xFF9CA3AF)),
                filled: true,
                fillColor: const Color(0xFFF9FAFB),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 10,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: const BorderSide(color: Color(0xFFE5E7EB), width: 0.5),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: const BorderSide(color: Color(0xFFE5E7EB), width: 0.5),
                ),
                // border turns blue when you tap the input
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: const BorderSide(color: Color(0xFF1A56DB), width: 1),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          // circular blue send button
          GestureDetector(
            onTap: () => _sendMessage(_controller.text),
            child: Container(
              width: 42,
              height: 42,
              decoration: const BoxDecoration(
                color: Color(0xFF1A56DB),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.send_rounded,
                color: Colors.white,
                size: 18,
              ),
            ),
          ),
        ],
      ),
    );
  }
}