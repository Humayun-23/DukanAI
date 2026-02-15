"""
Voice-to-Text Service for Indian Languages
Using Google Cloud Speech-to-Text with Hindi/English support
"""

from google.cloud import speech_v1 as speech
from google.cloud import translate_v2 as translate
from typing import Dict, Any
import os

class VoiceService:
    """Voice-to-text processing for Indian languages"""
    
    def __init__(self):
        # Initialize Google Cloud clients
        # Set GOOGLE_APPLICATION_CREDENTIALS env variable for authentication
        try:
            self.speech_client = speech.SpeechClient()
            self.translate_client = translate.Client()
        except Exception as e:
            print(f"⚠️ Google Cloud not configured: {e}")
            self.speech_client = None
            self.translate_client = None
    
    async def transcribe_audio(
        self,
        audio_file_path: str,
        language_code: str = 'hi-IN'  # Hindi by default
    ) -> Dict[str, Any]:
        """
        Transcribe audio file to text
        
        Supported language codes:
        - 'hi-IN': Hindi (India)
        - 'en-IN': English (India)
        - 'ta-IN': Tamil (India)
        - 'te-IN': Telugu (India)
        - 'mr-IN': Marathi (India)
        """
        
        if not self.speech_client:
            return {
                'success': False,
                'error': 'Speech client not configured'
            }
        
        try:
            # Read audio file
            with open(audio_file_path, 'rb') as audio_file:
                content = audio_file.read()
            
            audio = speech.RecognitionAudio(content=content)
            
            # Configure recognition with Indian language support
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                sample_rate_hertz=16000,
                language_code=language_code,
                alternative_language_codes=['en-IN', 'hi-IN'],  # Multi-language support
                enable_automatic_punctuation=True,
                model='default',  # Use default model for best accuracy
            )
            
            # Perform transcription
            response = self.speech_client.recognize(config=config, audio=audio)
            
            if not response.results:
                return {
                    'success': False,
                    'error': 'No transcription results'
                }
            
            # Extract best transcript
            transcript = response.results[0].alternatives[0].transcript
            confidence = response.results[0].alternatives[0].confidence
            
            # Detect language
            detected_language = self.detect_language(transcript)
            
            return {
                'success': True,
                'transcript': transcript,
                'confidence': confidence,
                'language': detected_language,
                'language_code': language_code
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Transcription failed: {str(e)}'
            }
    
    async def transcribe_with_auto_language(
        self,
        audio_file_path: str
    ) -> Dict[str, Any]:
        """
        Transcribe with automatic language detection
        Tries Hindi first, then English
        """
        
        # Try Hindi first (most common in India)
        result = await self.transcribe_audio(audio_file_path, 'hi-IN')
        
        if result['success'] and result['confidence'] > 0.8:
            return result
        
        # Try English if Hindi confidence is low
        result_en = await self.transcribe_audio(audio_file_path, 'en-IN')
        
        # Return result with higher confidence
        if result_en['success'] and result_en['confidence'] > result.get('confidence', 0):
            return result_en
        
        return result
    
    def detect_language(self, text: str) -> str:
        """Detect language of transcribed text"""
        
        if not self.translate_client:
            return 'unknown'
        
        try:
            detection = self.translate_client.detect_language(text)
            return detection['language']
        except:
            return 'unknown'
    
    async def translate_to_english(self, text: str, source_lang: str = 'hi') -> Dict[str, Any]:
        """Translate text to English"""
        
        if not self.translate_client:
            return {
                'success': False,
                'error': 'Translation client not configured'
            }
        
        try:
            result = self.translate_client.translate(
                text,
                source_language=source_lang,
                target_language='en'
            )
            
            return {
                'success': True,
                'original': text,
                'translated': result['translatedText'],
                'source_language': source_lang
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Translation failed: {str(e)}'
            }
    
    async def translate_to_hindi(self, text: str, source_lang: str = 'en') -> Dict[str, Any]:
        """Translate text to Hindi"""
        
        if not self.translate_client:
            return {
                'success': False,
                'error': 'Translation client not configured'
            }
        
        try:
            result = self.translate_client.translate(
                text,
                source_language=source_lang,
                target_language='hi'
            )
            
            return {
                'success': True,
                'original': text,
                'translated': result['translatedText'],
                'target_language': 'hi'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Translation failed: {str(e)}'
            }


# Fallback: Simple voice command patterns for common Indian business phrases
class SimpleVoiceCommandParser:
    """Fallback parser when Google Cloud is not available"""
    
    COMMAND_PATTERNS = {
        'invoice': [
            r'(?:ko|को)\s+(\d+)\s+(?:rupees?|rupay|रुपये?)\s+(?:ka|का)\s+(?:bill|invoice)',
            r'(?:bill|invoice)\s+(?:bhej|send|भेज)\s+(?:do|दो)',
        ],
        'payment': [
            r'(?:ne|ने)\s+(\d+)\s+(?:pay|payment|भुगतान)\s+(?:kiya|किया)',
            r'(?:payment|भुगतान)\s+(?:aaya|आया|received)',
        ],
        'stock': [
            r'(?:kitna|कितना)\s+(?:stock|स्टॉक)',
            r'(?:add|जोड़|add\s+kar)\s+(\d+)\s+(\w+)',
        ],
        'reminder': [
            r'(?:reminder|याद\s+दिला)\s+(?:bhej|send|भेज)',
            r'(?:pending|बकाया)\s+(?:payments?|भुगतान)',
        ]
    }
    
    def parse_command(self, text: str) -> Dict[str, Any]:
        """Parse voice command using regex patterns"""
        
        import re
        
        text_lower = text.lower()
        
        for intent, patterns in self.COMMAND_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match:
                    return {
                        'intent': intent,
                        'confidence': 0.7,
                        'matches': match.groups() if match.groups() else []
                    }
        
        return {
            'intent': 'unknown',
            'confidence': 0.0,
            'matches': []
        }
