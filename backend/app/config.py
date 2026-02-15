import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    pghost= os.getenv("PGHOST")
    pgport = os.getenv("PGPORT")
    pgpassword = os.getenv("PGPASSWORD")
    pgdatabase = os.getenv("PGDATABASE")
    pguser = os.getenv("PGUSER")
    pgsslmode = os.getenv("PGSSLMODE")
    pgchannelbinding = os.getenv("PGCHANNELBINDING")
    database_url = os.getenv("DATABASE_URL")

settings = Settings()