"""Helpers de interface compartilhados pelas páginas (mensagens e configuração)."""

import logging

import streamlit as st

from services.result import DataLoadError

logger = logging.getLogger(__name__)

_FLASH_KEY = "_flash_messages"


def setup_page(title: str, icon: str, layout: str = "wide") -> None:
    st.set_page_config(page_title=f"{title} · CRM Agentes de IA", page_icon=icon, layout=layout)


def flash(kind: str, message: str) -> None:
    """Agenda uma mensagem para ser exibida após o próximo st.rerun()."""
    st.session_state.setdefault(_FLASH_KEY, []).append((kind, message))


def show_flash() -> None:
    for kind, message in st.session_state.pop(_FLASH_KEY, []):
        getattr(st, kind)(message)


def handle_result(result, success_message: str) -> bool:
    """Exibe o erro do ServiceResult ou agenda sucesso/aviso. True se a operação foi realizada."""
    if result.error:
        st.error(result.error)
        return False
    flash("success", success_message)
    if result.warning:
        flash("warning", result.warning)
    return True


def load_or_stop(loader, *args):
    """Executa uma leitura; em falha, mostra erro + botão Recarregar e interrompe a página (Req 6.5)."""
    try:
        return loader(*args)
    except DataLoadError as exc:
        message = f"Falha no carregamento dos dados. {exc}"
    except Exception:
        logger.exception("Falha inesperada ao carregar dados")
        message = "Falha no carregamento dos dados. Tente novamente."
    st.error(message)
    if st.button("Recarregar", type="primary"):
        st.rerun()
    st.stop()
