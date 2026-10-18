from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from auth.login_guard import LoginGuard


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


def make_guard():
    clock = FakeClock()
    return LoginGuard(max_attempts=5, lockout=timedelta(minutes=15), clock=clock), clock


def test_quatro_falhas_nao_bloqueiam():
    guard, _ = make_guard()
    for _ in range(4):
        guard.register_failure("ana@x.com")
    assert guard.check("ana@x.com") == (False, 0)


def test_quinta_falha_bloqueia_por_15_minutos():
    guard, clock = make_guard()
    for _ in range(5):
        guard.register_failure("ana@x.com")
    locked, seconds = guard.check("ana@x.com")
    assert locked and seconds == 15 * 60

    clock.advance(minutes=14, seconds=59)
    assert guard.check("ana@x.com")[0] is True

    clock.advance(seconds=1)
    assert guard.check("ana@x.com") == (False, 0)


def test_contagem_zera_apos_expirar_bloqueio():
    guard, clock = make_guard()
    for _ in range(5):
        guard.register_failure("ana@x.com")
    clock.advance(minutes=15)
    guard.register_failure("ana@x.com")
    assert guard.check("ana@x.com")[0] is False


def test_falhas_durante_bloqueio_nao_estendem():
    guard, clock = make_guard()
    for _ in range(5):
        guard.register_failure("ana@x.com")
    clock.advance(minutes=10)
    guard.register_failure("ana@x.com")
    assert guard.check("ana@x.com")[1] == 5 * 60


def test_sucesso_zera_contagem():
    guard, _ = make_guard()
    for _ in range(4):
        guard.register_failure("ana@x.com")
    guard.register_success("ana@x.com")
    for _ in range(4):
        guard.register_failure("ana@x.com")
    assert guard.check("ana@x.com")[0] is False


def test_email_normalizado():
    guard, _ = make_guard()
    for email in ["Ana@X.com", " ana@x.com", "ANA@X.COM ", "ana@x.com", "aNa@x.Com"]:
        guard.register_failure(email)
    assert guard.check("ana@x.com")[0] is True


def test_emails_isolados():
    guard, _ = make_guard()
    for _ in range(5):
        guard.register_failure("ana@x.com")
    assert guard.check("bia@x.com") == (False, 0)


# Feature: crm-agentes-ia, Property 11: Bloqueio de login após 5 falhas consecutivas
@given(
    events=st.lists(
        st.tuples(st.sampled_from(["fail", "success"]), st.sampled_from(["ana@x.com", "ANA@x.com ", "bia@x.com"])),
        max_size=30,
    )
)
@settings(max_examples=100)
def test_property_11_bloqueio_apos_5_falhas(events):
    guard, _ = make_guard()  # relógio parado: nenhum bloqueio expira durante o teste
    consecutive: dict[str, int] = {}
    locked: set[str] = set()
    for kind, email in events:
        key = LoginGuard.normalize(email)
        if kind == "fail":
            guard.register_failure(email)
            if key not in locked:
                consecutive[key] = consecutive.get(key, 0) + 1
                if consecutive[key] >= 5:
                    locked.add(key)
        else:
            # Na aplicação, sucesso só é possível sem bloqueio; o guard zera a contagem.
            guard.register_success(email)
            consecutive.pop(key, None)
            locked.discard(key)
        for other in {"ana@x.com", "bia@x.com"}:
            assert guard.check(other)[0] == (other in locked)
