"""Correção opcional dos itens da lista após conferência do cupom."""
import streamlit as st
from receipt_audit import money, suggest_correction


def render_price_editor(receipt_lines, current, choices, signature, edit_item):
    st.markdown("#### 3. Corrigir itens da lista (opcional)")
    st.caption("Selecione apenas os itens que deseja alterar. Confira os valores antes de salvar.")
    if not choices:
        st.info("Vincule um produto do documento à sua lista para habilitar a correção.")
        return

    by_id = {str(row["id"]): row for row in current}
    grouped = {}
    for position, item_id in choices.items():
        if str(item_id) in by_id:
            grouped.setdefault(str(item_id), []).append(receipt_lines[position])

    if st.session_state.pop("receipt_update_notice", None):
        st.success("Itens selecionados atualizados. Os demais produtos foram preservados.")

    signature_short = signature[1][:12]
    revision = int(st.session_state.get("receipt_edit_revision", 0))
    edits = []

    with st.form("receipt_apply_changes_form"):
        for item_id, lines in grouped.items():
            item = by_id[item_id]
            name = item.get("produto_escolhido") or item.get("nome_produto") or "Produto"
            proposed = suggest_correction(
                lines, item.get("quantidade"), item.get("preco_unitario")
            )
            quantity_value = proposed["quantity"]
            price_value = proposed["unit_price"]
            suffix = f"{signature_short}_{revision}_{item_id}"
            with st.expander(f"{name} · {len(lines)} linha(s) no documento"):
                apply_this = st.checkbox(
                    "Atualizar este produto", value=False, key=f"receipt_apply_{suffix}"
                )
                if proposed["alert"]:
                    st.warning(proposed["alert"])
                st.caption(
                    f"No app: {item.get('quantidade')} {item.get('unidade', 'un.')} "
                    f"× {money(item.get('preco_unitario'))}; "
                    f"total do documento: {money(proposed['document_total'])}"
                )
                left, right = st.columns(2)
                qty = left.number_input(
                    "Quantidade para salvar", min_value=0.001, max_value=999999.999,
                    value=float(quantity_value) if quantity_value is not None else 1.0,
                    step=0.001, format="%.3f", key=f"receipt_edit_qty_{suffix}"
                )
                fractional_digits = (
                    len(str(price_value).partition(".")[2]) if price_value is not None else 2
                )
                price = right.number_input(
                    "Preço unitário pago (R$)", min_value=0.0, max_value=999999.0,
                    value=float(price_value) if price_value is not None else 0.0,
                    step=0.0001 if fractional_digits > 2 else 0.01,
                    format="%.4f" if fractional_digits > 2 else "%.2f",
                    key=f"receipt_edit_price_{suffix}"
                )
                checked_ok = st.checkbox(
                    "Manter/marcar como OK", value=bool(item.get("confirmado")),
                    key=f"receipt_edit_ok_{suffix}"
                )
                st.caption(f"Total proposto: {money(qty * price)}. Verifique descontos e itens por peso.")
                if apply_this:
                    edits.append((item, qty, price, checked_ok))

        submitted = st.form_submit_button(
            "Salvar alterações selecionadas na minha lista",
            type="primary", use_container_width=True
        )

    if submitted:
        if not edits:
            st.warning("Marque pelo menos um item para atualizar.")
            return
        saved = 0
        try:
            for item, qty, price, checked_ok in edits:
                edit_item(
                    item["id"], quantidade=qty, preco_unitario=price,
                    confirmado=checked_ok
                )
                saved += 1
        except Exception as exc:
            st.error(
                f"Falha ao atualizar: {exc}. {saved} item(ns) podem já ter sido salvos. "
                "Recarregue a conferência antes de tentar novamente."
            )
        else:
            st.session_state["receipt_edit_revision"] = revision + 1
            st.session_state["receipt_update_notice"] = saved
            st.rerun()
