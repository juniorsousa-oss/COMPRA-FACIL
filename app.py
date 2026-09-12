from pathlib import Path
import urllib.request
import streamlit as st

# Mantém toda a versão já validada do app e acrescenta apenas a identificação
# do supermercado no momento da finalização da compra.
BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/1e4ada77cce7266f607ef7712c2714046ddecf6d/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

_original_button = st.button

def _button_with_market(label, *args, **kwargs):
    clicked = _original_button(label, *args, **kwargs)
    if label == "Finalizar e salvar compra" and clicked:
        st.session_state["finish_market_requested"] = True
        return False
    return clicked

# Impede que o fluxo antigo finalize imediatamente. Ao clicar em finalizar,
# abrimos primeiro a identificação do supermercado.
st.button = _button_with_market
try:
    exec(compile(source, str(Path(__file__)), "exec"), globals(), globals())
finally:
    st.button = _original_button


def _finish_with_market(items, purchase_budget, market):
    """Executa a finalização já existente e injeta o supermercado no registro."""
    _original_db = globals()["db"]

    def _db_with_market(table, method="GET", params=None, data=None):
        if table == "compras" and method == "POST" and isinstance(data, dict):
            data = dict(data)
            data["supermercado"] = market.strip()
        return _original_db(table, method, params, data)

    globals()["db"] = _db_with_market
    try:
        return globals()["finish"](items, purchase_budget)
    finally:
        globals()["db"] = _original_db


@st.dialog("Finalizar compra")
def _market_dialog():
    st.markdown("### Onde esta compra foi realizada?")
    st.caption("O supermercado ficará vinculado ao histórico desta compra para permitir comparações futuras de preços e gastos por estabelecimento.")

    _known_markets = sorted({
        str(p.get("supermercado") or "").strip()
        for p in globals().get("history", [])
        if str(p.get("supermercado") or "").strip()
    }, key=str.lower)

    _market = ""
    if _known_markets:
        _choice = st.selectbox(
            "Supermercado",
            ["Selecione..."] + _known_markets + ["Outro supermercado"],
            key="finish_market_choice",
        )
        if _choice == "Outro supermercado":
            _market = st.text_input(
                "Nome do supermercado",
                placeholder="Ex.: Supermercado X",
                key="finish_market_other",
            ).strip()
        elif _choice != "Selecione...":
            _market = _choice
    else:
        _market = st.text_input(
            "Supermercado",
            placeholder="Ex.: Supermercado X",
            key="finish_market_first",
        ).strip()

    _a, _b = st.columns(2)
    if _a.button("Cancelar", use_container_width=True, key="cancel_finish_market"):
        st.session_state.pop("finish_market_requested", None)
        st.rerun()

    if _b.button("Finalizar compra", type="primary", use_container_width=True, key="confirm_finish_market"):
        if not _market:
            st.error("Informe o supermercado onde a compra foi realizada.")
        else:
            try:
                _finish_with_market(globals().get("current", []), globals().get("budget", 0), _market)
                st.session_state.pop("finish_market_requested", None)
                st.session_state.pop("finish_market_choice", None)
                st.session_state.pop("finish_market_other", None)
                st.session_state.pop("finish_market_first", None)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao finalizar: {e}")


if st.session_state.get("finish_market_requested"):
    _market_dialog()
