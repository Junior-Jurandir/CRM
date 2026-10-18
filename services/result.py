from typing import Any, NamedTuple


class ServiceResult(NamedTuple):
    """Resultado das operações de escrita dos serviços de dados.

    data:    registro criado, contagem ou True em caso de sucesso
    error:   mensagem para st.error() — a operação não foi realizada
    warning: mensagem para st.warning() — a operação foi realizada (ex.: cache não invalidado)
    """

    data: Any = None
    error: str | None = None
    warning: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class DataLoadError(RuntimeError):
    """Falha de leitura. Lançada (e não retornada) para que o erro não seja cacheado."""
