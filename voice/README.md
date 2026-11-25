# AIHive Voice Assistant MVP

**General knowledge voice bot supporting Thai and English**

A conversational AI assistant that processes voice or text input, answers questions in Thai or English, and provides information about AIHive's suite of applications.

## 🎯 Features

### Core Capabilities
- 🎤 **Voice Input**: Record audio with browser microphone
- 💬 **Text Input**: Type messages as an alternative to voice
- 🗣️ **Speech-to-Text**: OpenAI Whisper transcription
- 🤖 **AI Response**: GPT-4o-mini for general knowledge Q&A
- 🎧 **Text-to-Speech**: OpenAI TTS for spoken responses
- 🌏 **Bilingual**: Automatic Thai/English language detection

### AIHive Knowledge
The assistant can explain AIHive's applications:
- **Coach**: Personal development coaching with GROW framework
- **Tutor**: Step-by-step learning on any topic
- **Workforce Hub**: Team activity tracking and management
- **Marketing**: Campaign planning and optimization

### Safety & Privacy
- ✅ No financial investment advice
- ✅ No medical diagnosis
- ✅ No legal advice
- ✅ Session-only memory (no persistent storage)
- ✅ No audio files saved
- ✅ User isolation per session
- ✅ Cost guards: max 50 turns per session

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API key (optional - will use Demo Mode without it)

### Installation

1. **Install dependencies**:
   ```bash
   cd voice
   pip install -r requirements.txt
   ```

2. **Configure environment** (optional):
   ```bash
   # In the root directory
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Run the app**:
   ```bash
   streamlit run app.py
   ```

4. **Open your browser** to `http://localhost:8501`

### Demo Mode

If no `OPENAI_API_KEY` is provided, the app runs in **Demo Mode**:
- ✅ UI fully functional
- ✅ Scripted responses (clearly labeled "Demo mode")
- ✅ Text-only (no real audio transcription or synthesis)
- ✅ No API costs

## 🧪 Testing

### Run Unit Tests
```bash
# From voice/ directory
pytest tests/test_voice_ai.py -v
```

### Run E2E Tests
```bash
# Install Playwright browsers (first time only)
playwright install chromium

# Run E2E test
pytest tests/test_e2e_voice.py -v
```

The E2E test captures screenshots to `/tmp` (not committed):
- Voice assistant initial state
- Mid-conversation
- Response with audio (AI mode)

### Test Coverage
- STT/LLM/TTS pipeline with mocked OpenAI
- Thai and English language handling
- Demo mode labeling
- Safety checks (no financial/medical/legal advice)
- Cost guard enforcement
- API key security (never in output)

## 💰 Cost Estimation

### OpenAI Pricing (as of 2026)
- **Whisper (STT)**: $0.006 per minute
- **GPT-4o-mini**: $0.00015/1K input tokens, $0.0006/1K output tokens
- **TTS-1**: $15 per 1M characters

### Per-Turn Estimate (voice input + response)
- Audio transcription (10 seconds): ~$0.001
- LLM response (~150 input, ~80 output tokens): ~$0.00007
- TTS response (100 characters): ~$0.0015
- **Total per voice turn**: ~$0.0026 USD (0.26 cents)

### Session Projections
- **10 voice turns**: ~$0.026 (about 2.6 cents)
- **50 voice turns** (session max): ~$0.13 (13 cents)

### Monthly Estimates
- **100 users** (5 sessions/month, 10 turns each): ~$13/month
- **1,000 users** (5 sessions/month, 10 turns each): ~$130/month

**Cost Controls**:
- Maximum 50 turns per session
- Text-only mode uses less (no STT/TTS)
- Demo mode: $0 cost

## 🏗️ Architecture

### Tech Stack
- **Frontend**: Streamlit with `st.audio_input` and `st.audio`
- **AI Models**:
  - OpenAI Whisper (speech-to-text)
  - GPT-4o-mini (chat)
  - TTS-1 (text-to-speech)
- **Language Detection**: Character-based heuristics + Whisper language output

### File Structure
```
voice/
├── app.py                      # Main Streamlit app
├── voice_ai.py                 # OpenAI integration (STT/LLM/TTS)
├── requirements.txt            # Dependencies
├── README.md                   # This file
└── tests/
    ├── __init__.py
    ├── test_voice_ai.py        # Unit tests (mocked OpenAI)
    └── test_e2e_voice.py       # E2E test (Playwright)
```

### Session Management
- Each browser session gets a unique UUID
- Conversation history limited to last 20 messages (cost optimization)
- No cross-session or cross-user data sharing
- Audio files never stored server-side

### Cost Logging
All API costs are logged to stdout (numbers only, no content):
```
[COST] STT: {'model': 'whisper-1', 'audio_seconds': 5.2, 'cost_usd': 0.00052}
[COST] LLM: {'model': 'gpt-4o-mini', 'input_tokens': 150, 'output_tokens': 80, 'cost_usd': 0.00007}
[COST] TTS: {'model': 'tts-1', 'characters': 95, 'cost_usd': 0.0000014}
```

## 🔒 Security & Privacy

### API Key Management
- ✅ Loaded from environment variables server-side only
- ✅ Never exposed in frontend code
- ✅ Never logged or displayed to users

### Content Safety
- ❌ No financial investment advice
- ❌ No medical diagnosis
- ❌ No legal advice
- ✅ Safety filter checks every user message
- ✅ Polite refusal + professional referral when violated

### Data Privacy
- Session-scoped conversation history (not persisted)
- No audio recordings saved
- No user identification or tracking
- Each session isolated by UUID

## 📋 Limitations & Future Work

### Current MVP Limitations
- No authentication (browser session only)
- No conversation history persistence
- No multi-turn context optimization
- Text-based language detection (heuristic)
- Fixed voice selection (not customizable)
- No voice activity detection (VAD)
- No streaming audio responses

### Recommended Enhancements
1. **Streaming responses** for lower latency
2. **VAD** for automatic recording start/stop
3. **Persistent conversation history** with user accounts
4. **Custom voice selection** per user preference
5. **Advanced language detection** (multilingual support beyond Thai/English)
6. **Cost dashboards** for usage monitoring
7. **Conversation export** for review
8. **Integration with other AIHive apps** (deep linking)

## 🤝 Integration with AIHive Suite

This voice assistant acts as a **general entry point** to the AIHive ecosystem:

- Ask about **Coach** → Assistant explains and can suggest navigating to it
- Ask about **Tutor** → Assistant explains topics and learning approach
- Ask about **Workforce** → Assistant explains team management features
- Ask about **Marketing** → Assistant explains campaign planning

Future versions could enable:
- Voice commands to launch specific apps
- Voice-based coaching sessions
- Voice Q&A for learning topics
- Voice dictation for marketing content

## 📄 License

© 2026 AIHiveHQ. Founded by Rungnapa Mukdasanit.

## 🆘 Support

For questions or issues:
- Founder: Rungnapa Mukdasanit
- Website: https://aihivehq.com (coming soon)
