"""Controle de tentativas de login por e-mail (Req 1.6).

Módulo puro (sem Streamlit). Uma instância é compartilhada por todas as
sessões do processo (ver auth.authentication._login_guard), de modo que
recarregar a página ou abrir outra aba não zera a contagem.

Limitação: o estado vive na memória do processo; é perdido ao reiniciar o
servidor e não é compartilhado entre múltiplas instâncias do app.
"""

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _Entry:
    failures: int = 0
    locked_until: datetime | None = None


class LoginGuard:
    def __init__(
        self,
        max_attempts: int = 5,
        lockout: timedelta = timedelta(minutes=15),
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._max_attempts = max_attempts
        self._lockout = lockout
        self._clock = clock
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def normalize(email: str | None) -> str:
        return (email or "").strip().lower()

    def _active_entry(self, key: str) -> _Entry | None:
        """Retorna a entrada do e-mail, descartando-a se o bloqueio já expirou."""
        entry = self._entries.get(key)
        if entry and entry.locked_until and self._clock() >= entry.locked_until:
            del self._entries[key]
            return None
        return entry

    def check(self, email: str) -> tuple[bool, int]:
        """(bloqueado?, segundos restantes de bloqueio)."""
        key = self.normalize(email)
        with self._lock:
            entry = self._active_entry(key)
            if entry and entry.locked_until:
                remaining = (entry.locked_until - self._clock()).total_seconds()
                return True, max(1, math.ceil(remaining))
            return False, 0

    def register_failure(self, email: str) -> None:
        key = self.normalize(email)
        with self._lock:
            entry = self._active_entry(key) or self._entries.setdefault(key, _Entry())
            if entry.locked_until:
                return  # já bloqueado: não estende o bloqueio
            entry.failures += 1
            if entry.failures >= self._max_attempts:
                entry.locked_until = self._clock() + self._lockout

    def register_success(self, email: str) -> None:
        with self._lock:
            self._entries.pop(self.normalize(email), None)
