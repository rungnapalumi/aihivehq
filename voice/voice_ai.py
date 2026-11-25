"""
AIHive Voice Assistant AI Logic
Handles STT, LLM, and TTS with OpenAI + demo mode
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aihive_coach.config import config
from typing import Tuple, Optional
import io


class VoiceAI:
    """Voice AI that handles speech-to-text, chat, and text-to-speech"""
    
    def __init__(self):
        self.is_demo = config.is_demo_mode()
        if not self.is_demo:
            try:
                import openai
                self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            except ImportError:
                self.is_demo = True
        
        # Safety guardrails - expanded patterns
        self.forbidden_topics = [
            "investment advice", "financial advice", "stock picks", "stocks",
            "medical diagnosis", "legal advice", "prescription",
            "invest", "diagnose"
        ]
    
    def transcribe_audio(self, audio_bytes: bytes, audio_format: str = "wav") -> Tuple[str, str, dict]:
        """
        Transcribe audio to text and detect language.
        Returns: (transcript_text, detected_language, cost_info)
        """
        if self.is_demo:
            return self._demo_transcribe(audio_bytes)
        else:
            return self._ai_transcribe(audio_bytes, audio_format)
    
    def generate_response(
        self, 
        user_message: str, 
        language: str, 
        conversation_history: list
    ) -> Tuple[str, dict]:
        """
        Generate AI response based on user message and conversation history.
        Returns: (response_text, cost_info)
        """
        if self.is_demo:
            return self._demo_generate_response(user_message, language)
        else:
            return self._ai_generate_response(user_message, language, conversation_history)
    
    def synthesize_speech(self, text: str, language: str) -> Tuple[bytes, dict]:
        """
        Convert text to speech audio.
        Returns: (audio_bytes, cost_info)
        """
        if self.is_demo:
            return self._demo_synthesize_speech(text, language)
        else:
            return self._ai_synthesize_speech(text, language)
    
    def check_safety(self, text: str) -> bool:
        """
        Check if text contains forbidden topics.
        Returns: True if safe, False if forbidden
        """
        text_lower = text.lower()
        for topic in self.forbidden_topics:
            if topic in text_lower:
                return False
        return True
    
    # Demo Mode Implementations
    
    def _demo_transcribe(self, audio_bytes: bytes) -> Tuple[str, str, dict]:
        """Demo mode: return scripted transcription"""
        # Simulate transcription based on audio length
        audio_length_seconds = len(audio_bytes) / 16000  # Rough estimate
        
        if audio_length_seconds < 2:
            transcript = "สวัสดีค่ะ"  # Hello in Thai
            language = "th"
        elif audio_length_seconds < 4:
            transcript = "What is AIHive?"
            language = "en"
        else:
            transcript = "Tell me about the tutor app"
            language = "en"
        
        cost_info = {
            "model": "demo",
            "audio_seconds": round(audio_length_seconds, 2),
            "cost_usd": 0.0
        }
        
        return (transcript, language, cost_info)
    
    def _demo_generate_response(self, user_message: str, language: str) -> Tuple[str, dict]:
        """Demo mode: return scripted responses"""
        message_lower = user_message.lower()
        
        # Detect language keywords
        is_thai = any(char in user_message for char in "กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
        
        if is_thai or language == "th":
            # Thai responses
            if "สวัสดี" in message_lower or "hello" in message_lower:
                response = "สวัสดีค่ะ! ฉันคือ AIHive Voice Assistant ฉันพร้อมช่วยตอบคำถามเกี่ยวกับเรื่องทั่วไป และแนะนำแอปของ AIHive ค่ะ"
            elif "aihive" in message_lower:
                response = "AIHive มีแอปหลายตัว: Coach สำหรับโค้ชชิ่งส่วนตัว, Tutor สำหรับการเรียนรู้, Workforce Hub สำหรับจัดการทีม, และ Marketing สำหรับแคมเปญการตลาด ค่ะ"
            elif "tutor" in message_lower:
                response = "AIHive Tutor เป็นติวเตอร์ AI ที่สอนทีละขั้นตอน รองรับหลายหัวข้อและหลายระดับความยาก ค่ะ"
            else:
                response = "นั่นเป็นคำถามที่ดีค่ะ ในโหมดสาธิต ฉันให้คำตอบแบบสคริปต์ ในโหมด AI จริง ฉันจะตอบคำถามได้หลากหลายมากขึ้นค่ะ"
        else:
            # English responses
            if "hello" in message_lower or "hi" in message_lower:
                response = "Hello! I'm AIHive Voice Assistant. I can answer general questions and tell you about AIHive's apps: Coach, Tutor, Workforce Hub, and Marketing."
            elif "aihive" in message_lower:
                response = "AIHive has four main applications: Coach for personal development coaching, Tutor for step-by-step learning, Workforce Hub for team management, and Marketing for campaign planning. What would you like to know more about?"
            elif "coach" in message_lower:
                response = "AIHive Coach helps you think through goals, challenges, and decisions using a GROW-inspired coaching framework. It asks thoughtful questions and helps you create action plans."
            elif "tutor" in message_lower:
                response = "AIHive Tutor is an AI study tutor that teaches topics step-by-step at Beginner, Intermediate, or Advanced levels. It checks your understanding and adapts explanations based on your progress."
            elif "workforce" in message_lower:
                response = "AIHive Workforce Hub helps teams track activities, manage resources, and coordinate work. It's designed for team collaboration and productivity tracking."
            elif "marketing" in message_lower:
                response = "AIHive Marketing helps you plan and track marketing campaigns with AI-powered insights for messaging, targeting, and optimization."
            else:
                response = "That's a good question! In demo mode, I provide scripted answers. With real AI mode, I can answer a much wider range of questions about any topic."
        
        cost_info = {
            "model": "demo",
            "input_tokens": len(user_message.split()),
            "output_tokens": len(response.split()),
            "cost_usd": 0.0
        }
        
        return (response, cost_info)
    
    def _demo_synthesize_speech(self, text: str, language: str) -> Tuple[bytes, dict]:
        """Demo mode: return empty audio bytes (no actual audio)"""
        # In demo mode, we don't generate real audio
        # Return empty bytes - the UI will show text only
        cost_info = {
            "model": "demo",
            "characters": len(text),
            "cost_usd": 0.0
        }
        
        return (b"", cost_info)
    
    # Real AI Implementations
    
    def _ai_transcribe(self, audio_bytes: bytes, audio_format: str) -> Tuple[str, str, dict]:
        """Real AI: use OpenAI Whisper for transcription"""
        # Create a file-like object from bytes
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{audio_format}"
        
        # Transcribe with OpenAI Whisper
        response = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json"
        )
        
        transcript = response.text.strip()
        detected_language = getattr(response, 'language', 'en')
        
        # Estimate cost (Whisper is $0.006 per minute)
        audio_duration_seconds = len(audio_bytes) / 16000  # Rough estimate for 16kHz audio
        audio_duration_minutes = audio_duration_seconds / 60.0
        cost_usd = audio_duration_minutes * 0.006
        
        cost_info = {
            "model": "whisper-1",
            "audio_seconds": round(audio_duration_seconds, 2),
            "cost_usd": round(cost_usd, 6)
        }
        
        return (transcript, detected_language, cost_info)
    
    def _ai_generate_response(
        self, 
        user_message: str, 
        language: str, 
        conversation_history: list
    ) -> Tuple[str, dict]:
        """Real AI: use OpenAI GPT for response generation"""
        
        # Build system prompt based on detected language
        if language == "th" or any(char in user_message for char in "กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"):
            system_prompt = """คุณคือ AIHive Voice Assistant ผู้ช่วยเสียงที่เป็นมิตรและมีความรู้กว้างขวาง

คุณสามารถ:
- ตอบคำถามทั่วไปในหัวข้อต่างๆ
- แนะนำแอปของ AIHive: Coach (โค้ชชิ่งส่วนตัว), Tutor (การเรียนรู้), Workforce Hub (จัดการทีม), Marketing (แคมเปญการตลาด)

ข้อจำกัดความปลอดภัย:
- ห้ามให้คำแนะนำการลงทุนหรือการเงิน
- ห้ามวินิจฉัยทางการแพทย์หรือให้คำปรึกษากฎหมาย
- หากถูกถาม ให้บอกว่าคุณไม่สามารถช่วยในเรื่องนั้นได้ และแนะนำให้ปรึกษาผู้เชี่ยวชาญ

ตอบสั้นและชัดเจน (2-3 ประโยค) เพราะนี่คือการสนทนาด้วยเสียง"""
        else:
            system_prompt = """You are AIHive Voice Assistant, a friendly and knowledgeable general assistant.

You can:
- Answer general questions on various topics
- Explain AIHive's apps: Coach (personal development coaching), Tutor (step-by-step learning), Workforce Hub (team management), Marketing (campaign planning)

Safety guardrails:
- NO investment or financial advice
- NO medical diagnosis or legal advice
- If asked, politely decline and suggest consulting a qualified professional

Keep responses SHORT and conversational (2-3 sentences) since this is voice interaction."""
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (limit to last 10 exchanges)
        for msg in conversation_history[-20:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        messages.append({"role": "user", "content": user_message})
        
        # Check safety
        if not self.check_safety(user_message):
            if language == "th":
                return ("ขอโทษค่ะ ฉันไม่สามารถให้คำแนะนำด้านการเงิน การแพทย์ หรือกฎหมายได้ กรุณาปรึกษาผู้เชี่ยวชาญที่มีใบอนุญาตค่ะ", 
                       {"model": "safety-filter", "cost_usd": 0.0})
            else:
                return ("I'm sorry, I can't provide financial, medical, or legal advice. Please consult a qualified professional.", 
                       {"model": "safety-filter", "cost_usd": 0.0})
        
        # Generate response
        response = self.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=300  # Keep responses concise for voice
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Calculate cost
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        # GPT-4o-mini pricing: $0.00015/1K input, $0.0006/1K output
        cost_usd = (input_tokens / 1000.0 * 0.00015) + (output_tokens / 1000.0 * 0.0006)
        
        cost_info = {
            "model": config.OPENAI_MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 6)
        }
        
        return (response_text, cost_info)
    
    def _ai_synthesize_speech(self, text: str, language: str) -> Tuple[bytes, dict]:
        """Real AI: use OpenAI TTS for speech synthesis"""
        
        # Choose voice based on language
        # OpenAI voices: alloy, echo, fable, onyx, nova, shimmer
        voice = "nova" if language == "th" else "alloy"
        
        # Generate speech
        response = self.client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        
        # Get audio bytes
        audio_bytes = response.content
        
        # Calculate cost (TTS-1 is $0.015 per 1M characters)
        characters = len(text)
        cost_usd = (characters / 1_000_000.0) * 0.015
        
        cost_info = {
            "model": "tts-1",
            "voice": voice,
            "characters": characters,
            "cost_usd": round(cost_usd, 6)
        }
        
        return (audio_bytes, cost_info)


# Global instance
voice_ai = VoiceAI()
