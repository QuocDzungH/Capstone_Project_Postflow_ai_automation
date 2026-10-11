"""Select SQLite for the local demo, or PostgreSQL via DATABASE_URL."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL.startswith(('postgresql://', 'postgres://')):
    from backend.storage.postgres import create_order, get_order, initialize, update_order
elif DATABASE_URL:
    raise ValueError('DATABASE_URL must be empty or a PostgreSQL URL.')
else:
    from backend.storage.sqlite import create_order, get_order, initialize, update_order
