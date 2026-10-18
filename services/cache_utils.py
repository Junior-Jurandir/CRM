import logging

logger = logging.getLogger(__name__)

CACHE_WARNING = "Dados podem estar desatualizados. Recarregue a página manualmente."


def safe_clear(*cached_functions) -> str | None:
    """Invalida o cache das funções informadas (Req 8.2).

    A escrita já foi confirmada pelo banco: uma falha aqui não a desfaz, apenas
    devolve um aviso para a UI (Req 8.3).
    """
    failed = False
    for fn in cached_functions:
        try:
            fn.clear()
        except Exception:
            logger.warning("Falha ao invalidar cache de %s", getattr(fn, "__name__", fn), exc_info=True)
            failed = True
    return CACHE_WARNING if failed else None


def clear_all_caches() -> str | None:
    """Botão "Atualizar dados": força a leitura do estado atual do banco."""
    from services import client_service, contract_service, scope_service

    return safe_clear(client_service.list_clients, contract_service.list_contracts, scope_service.get_scope_by_contract)
