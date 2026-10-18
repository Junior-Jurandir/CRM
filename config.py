"""Variáveis de ambiente e constantes globais.

Lê o arquivo .env (se existir) e as variáveis de ambiente do processo.
Não depende do Streamlit.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

CACHE_TTL = 300                     # segundos (Req 8.1)
SESSION_MAX_HOURS = 8               # Req 1.3, 1.5
TOKEN_REFRESH_MARGIN_SECONDS = 60   # renovação antecipada do token
LOGIN_MAX_ATTEMPTS = 5              # Req 1.6
LOGIN_LOCKOUT_MINUTES = 15          # Req 1.6
