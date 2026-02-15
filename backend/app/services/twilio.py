import requests
from pydub import AudioSegment
from app.config import settings

def download_audio(media_url):
    try:
        print(f"📥 Downloading audio from {media_url}...")
        # Twilio requires Basic Auth to download media
        response = requests.get(
            media_url, 
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        )
        
        if response.status_code == 200:
            with open("temp.ogg", "wb") as f:
                f.write(response.content)
            
            # Convert OGG -> MP3 for Gemini
            AudioSegment.from_file("temp.ogg", format="ogg").export("temp.mp3", format="mp3")
            return "temp.mp3"
        else:
            print(f"❌ Download Failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Audio Error: {e}")
        return None