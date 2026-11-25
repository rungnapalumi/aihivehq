"""
AIHive Voice Assistant - Main Streamlit App
General knowledge voice bot supporting Thai and English
"""
import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aihive_coach.config import config
from voice.voice_ai import voice_ai


# Session state initialization
def init_session_state():
    """Initialize session state variables"""
    if "voice_conversation" not in st.session_state:
        st.session_state.voice_conversation = []
    
    if "voice_turn_count" not in st.session_state:
        st.session_state.voice_turn_count = 0
    
    if "voice_total_cost" not in st.session_state:
        st.session_state.voice_total_cost = 0.0
    
    if "voice_session_id" not in st.session_state:
        import uuid
        st.session_state.voice_session_id = str(uuid.uuid4())


def check_rate_limit():
    """
    Check if user has exceeded rate limits (cost guard).
    Returns: (allowed, message)
    """
    MAX_TURNS = 50  # Max 50 exchanges per session
    MAX_AUDIO_MINUTES = 10  # Max 10 minutes of audio per session
    
    if st.session_state.voice_turn_count >= MAX_TURNS:
        return (False, f"Session limit reached: {MAX_TURNS} exchanges maximum. Please refresh to start a new session.")
    
    return (True, "")


def process_text_input(user_text: str, detected_language: str = "en"):
    """Process text input (from typing or transcription)"""
    # Check rate limit
    allowed, message = check_rate_limit()
    if not allowed:
        st.error(message)
        return
    
    # Add to conversation history
    st.session_state.voice_conversation.append({
        "role": "user",
        "content": user_text,
        "type": "text"
    })
    
    # Generate AI response
    with st.spinner("Thinking..."):
        response_text, cost_info = voice_ai.generate_response(
            user_text,
            detected_language,
            st.session_state.voice_conversation[:-1]  # Exclude current message
        )
    
    # Log cost
    if cost_info["cost_usd"] > 0:
        st.session_state.voice_total_cost += cost_info["cost_usd"]
        print(f"[COST] LLM: {cost_info}")
    
    # Add response to conversation
    st.session_state.voice_conversation.append({
        "role": "assistant",
        "content": response_text,
        "type": "text"
    })
    
    # Synthesize speech for response
    if not config.is_demo_mode():
        with st.spinner("Generating speech..."):
            audio_bytes, tts_cost_info = voice_ai.synthesize_speech(response_text, detected_language)
        
        if tts_cost_info["cost_usd"] > 0:
            st.session_state.voice_total_cost += tts_cost_info["cost_usd"]
            print(f"[COST] TTS: {tts_cost_info}")
        
        # Store audio for playback
        st.session_state.voice_conversation[-1]["audio"] = audio_bytes
    
    # Increment turn count
    st.session_state.voice_turn_count += 1


def show_voice_page():
    """Main voice assistant page"""
    init_session_state()
    
    # Header
    st.title("🎤 AIHive Voice Assistant")
    
    # Mode indicator
    if config.is_demo_mode():
        st.warning("⚠️ **Demo Mode** – Scripted responses, no real AI or audio (text only)")
    else:
        st.success("✅ **Real AI Active** – Powered by OpenAI (Whisper + GPT-4o-mini + TTS)")
    
    st.markdown("---")
    
    # Info section
    with st.expander("ℹ️ About this assistant"):
        st.markdown("""
        **AIHive Voice Assistant** is a general knowledge assistant that can:
        
        - 🌍 Answer questions in **Thai** and **English**
        - 🗣️ Process voice input or typed text
        - 🎧 Respond with spoken audio (AI mode only)
        - 📚 Explain AIHive's apps:
          - **Coach**: Personal development coaching
          - **Tutor**: Step-by-step learning
          - **Workforce Hub**: Team management
          - **Marketing**: Campaign planning
        
        **Safety**: This assistant does not provide financial investment advice, medical diagnosis, or legal advice.
        
        **Privacy**: Conversations are kept in your browser session only. Audio is not stored.
        """)
    
    # Cost display (for transparency)
    if not config.is_demo_mode() and st.session_state.voice_total_cost > 0:
        st.caption(f"💰 Session cost: ${st.session_state.voice_total_cost:.4f} USD | Turns: {st.session_state.voice_turn_count}/50")
    
    # Conversation display
    st.markdown("### 💬 Conversation")
    
    if len(st.session_state.voice_conversation) == 0:
        st.info("👋 Say hello or ask a question to get started! You can speak or type.")
    else:
        for msg in st.session_state.voice_conversation:
            if msg["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(msg["content"])
                    
                    # Play audio if available
                    if "audio" in msg and len(msg["audio"]) > 0:
                        st.audio(msg["audio"], format="audio/mp3")
    
    st.markdown("---")
    
    # Input section
    st.markdown("### 🎙️ Your Turn")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Audio input
        audio_input = st.audio_input("🎤 Record your voice (or type below)")
        
        if audio_input is not None:
            # Process audio
            audio_bytes = audio_input.read()
            
            with st.spinner("Transcribing..."):
                transcript, detected_lang, stt_cost_info = voice_ai.transcribe_audio(
                    audio_bytes,
                    audio_format="wav"
                )
            
            # Log cost
            if stt_cost_info["cost_usd"] > 0:
                st.session_state.voice_total_cost += stt_cost_info["cost_usd"]
                print(f"[COST] STT: {stt_cost_info}")
            
            # Show transcript
            st.info(f"**You said ({detected_lang}):** {transcript}")
            
            # Process as text
            process_text_input(transcript, detected_lang)
            st.rerun()
    
    with col2:
        # Clear conversation button
        if st.button("🔄 New Conversation", use_container_width=True):
            st.session_state.voice_conversation = []
            st.session_state.voice_turn_count = 0
            st.session_state.voice_total_cost = 0.0
            import uuid
            st.session_state.voice_session_id = str(uuid.uuid4())
            st.rerun()
    
    # Text input alternative
    text_input = st.chat_input("💬 Or type your message here...")
    
    if text_input:
        # Detect language from text
        is_thai = any(char in text_input for char in "กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
        detected_lang = "th" if is_thai else "en"
        
        process_text_input(text_input, detected_lang)
        st.rerun()


if __name__ == "__main__":
    show_voice_page()
