"""Cliente Supabase falso para testes de repositório (sem rede).

Cada .execute() consome a próxima resposta da fila: uma lista de linhas
(ou outro valor de `data`) ou uma exceção a ser lançada.
"""

from types import SimpleNamespace

from postgrest.exceptions import APIError


def api_error(code: str, message: str = "erro") -> APIError:
    return APIError({"code": code, "message": message, "details": None, "hint": None})


class FakeQuery:
    def __init__(self, client: "FakeClient", target: str):
        self._client = client
        self.target = target
        self.calls: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self

        return method

    def execute(self):
        self._client.executed.append(self)
        if not self._client.responses:
            raise AssertionError(f"Nenhuma resposta configurada para {self.target} {self.calls}")
        result = self._client.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(data=result)

    # Conveniências para asserções
    def names(self) -> list[str]:
        return [name for name, _, _ in self.calls]

    def call(self, name: str) -> tuple[tuple, dict]:
        for n, args, kwargs in self.calls:
            if n == name:
                return args, kwargs
        raise AssertionError(f"{name} não foi chamado em {self.target}: {self.names()}")


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.executed: list[FakeQuery] = []

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rpc(self, fn: str, params: dict) -> FakeQuery:
        query = FakeQuery(self, f"rpc:{fn}")
        query.calls.append(("rpc", (fn, params), {}))
        return query

    @property
    def last(self) -> FakeQuery:
        return self.executed[-1]

    def all_method_names(self) -> set[str]:
        return {name for q in self.executed for name in q.names()}
