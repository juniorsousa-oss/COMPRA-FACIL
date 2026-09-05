import os
from datetime import datetime
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Compra Fácil", page_icon="🛒", layout="centered", initial_sidebar_state="collapsed")

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", "https://cuixazpxkvniqldmmnth.supabase.co"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))

if not SUPABASE_KEY:
    st.error("Supabase não configurado. No Streamlit Cloud, abra Settings → Secrets e informe SUPABASE_URL e SUPABASE_KEY.")
    st.stop()

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def api(table, method="GET", params=None, data=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = dict(HEADERS)
    if method in ("POST", "PATCH"):
        headers["Prefer"] = "return=representation"
    r = requests.request(method, url, headers=headers, params=params, json=data, timeout=15)
    if not r.ok:
        raise RuntimeError(f"Supabase {r.status_code}: {r.text[:500]}")
    return r.json() if r.text else []


def money(v):
    return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def load_products():
    return api("produtos", params={"select":"*", "order":"nome.asc"})


def load_current():
    return api("lista_atual", params={"select":"*", "order":"categoria.asc,nome_produto.asc"})


def load_budget():
    rows = api("estado_app", params={"select":"orcamento", "id":"eq.1"})
    return float(rows[0]["orcamento"]) if rows else 0.0


def set_budget(value):
    api("estado_app", "PATCH", params={"id":"eq.1"}, data={"orcamento": float(value), "atualizado_em": datetime.utcnow().isoformat()})


def add_product(name, category, unit, qty, estimated):
    api("lista_atual", "POST", data={
        "nome_produto": name.strip(), "categoria": category.strip() or "Mercearia",
        "unidade": unit.strip() or "un.", "quantidade": float(qty),
        "preco_estimado": float(estimated), "preco_unitario": 0,
    })


def update_item(item_id, **changes):
    api("lista_atual", "PATCH", params={"id":f"eq.{item_id}"}, data=changes)


def delete_item(item_id):
    api("lista_atual", "DELETE", params={"id":f"eq.{item_id}"})


def save_product(name, category, unit, price, quantity=1):
    existing = api("produtos", params={"select":"*", "nome":f"ilike.{name}"})
    if existing:
        p = existing[0]
        prices = [float(p.get("ultimo_preco") or 0), float(price)]
        update = {
            "categoria": category, "unidade": unit, "ultimo_preco": float(price),
            "preco_medio": sum(x for x in prices if x > 0) / max(1, len([x for x in prices if x > 0])),
            "menor_preco": min(x for x in prices if x > 0) if any(x > 0 for x in prices) else 0,
            "maior_preco": max(prices), "ultima_quantidade": float(quantity),
            "quantidade_compras": int(p.get("quantidade_compras") or 0) + 1,
            "atualizado_em": datetime.utcnow().isoformat(),
        }
        api("produtos", "PATCH", params={"id":f"eq.{p['id']}"}, data=update)
    else:
        api("produtos", "POST", data={
            "nome": name.strip(), "categoria": category, "unidade": unit,
            "ultimo_preco": float(price), "preco_medio": float(price),
            "menor_preco": float(price), "maior_preco": float(price),
            "ultima_quantidade": float(quantity), "quantidade_compras": 1,
        })


def finalize_purchase(items, budget):
    estimated = sum(float(i["quantidade"]) * float(i.get("preco_estimado") or 0) for i in items)
    real = sum(float(i["quantidade"]) * float(i.get("preco_unitario") or 0) for i in items if i.get("confirmado"))
    compra = api("compras", "POST", data={
        "orcamento": float(budget), "valor_estimado": estimated,
        "valor_real": real, "saldo": float(budget) - real,
        "quantidade_itens": len(items), "data_compra": datetime.utcnow().isoformat(),
    })[0]
    rows = []
    for i in items:
        unit_price = float(i.get("preco_unitario") or 0)
        est = float(i.get("preco_estimado") or 0)
        qty = float(i["quantidade"])
        rows.append({
            "compra_id": compra["id"], "produto_id": None,
            "nome_produto": i["nome_produto"], "quantidade": qty,
            "unidade": i["unidade"], "preco_estimado": est,
            "preco_unitario": unit_price, "valor_total": qty * unit_price,
            "ultimo_preco": est, "variacao_preco": unit_price - est,
            "confirmado": bool(i.get("confirmado")),
        })
        save_product(i["nome_produto"], i["categoria"], i["unidade"], unit_price or est, qty)
    if rows:
        api("itens_compra", "POST", data=rows)
    api("lista_atual", "DELETE", params={"id":"gt.0"})
    return compra


def history():
    return api("compras", params={"select":"*", "order":"data_compra.desc"})


def history_items(compra_id):
    return api("itens_compra", params={"select":"*", "compra_id":f"eq.{compra_id}", "order":"id.asc"})


def render_header():
    st.title("🛒 Compra Fácil")
    st.caption("V4 · Streamlit + Supabase · base única compartilhada")


render_header()

try:
    products = load_products()
    current = load_current()
    budget = load_budget()
except Exception as e:
    st.error(f"Não consegui acessar o banco: {e}")
    st.stop()

# Dashboard
estimated = sum(float(i["quantidade"]) * float(i.get("preco_estimado") or 0) for i in current)
real = sum(float(i["quantidade"]) * float(i.get("preco_unitario") or 0) for i in current if i.get("confirmado"))
items_done = sum(1 for i in current if i.get("confirmado"))

c1, c2 = st.columns(2)
c1.metric("Caixa", money(budget))
c2.metric("Estimado", money(estimated))
c3, c4 = st.columns(2)
c3.metric("Real", money(real))
c4.metric("Saldo real", money(budget - real))

if budget > 0:
    st.progress(min(real / budget, 1.0), text=f"Consumo real: {real / budget:.0%}")

st.info(f"Lista atual: **{items_done}/{len(current)} itens confirmados**")

# Navegação
aba = st.radio("Navegação", ["🛒 Compra", "📦 Produtos", "📜 Histórico", "📊 Análises", "⚙️ Configurações"], horizontal=True, label_visibility="collapsed")

if aba == "🛒 Compra":
    st.subheader("Lista atual")
    if current:
        for item in current:
            with st.container(border=True):
                a, b, c = st.columns([4, 1.2, 1])
                a.markdown(f"**{item['nome_produto']}**  ")
                a.caption(f"{item['categoria']} · {item['unidade']}")
                qty = b.number_input("Qtd", min_value=0.001, value=float(item["quantidade"]), step=1.0, key=f"q{item['id']}")
                if qty != float(item["quantidade"]):
                    update_item(item["id"], quantidade=qty)
                    st.rerun()
                checked = c.checkbox("OK", value=bool(item.get("confirmado")), key=f"c{item['id']}")
                if checked != bool(item.get("confirmado")):
                    update_item(item["id"], confirmado=checked)
                    st.rerun()
                d, e, f = st.columns([2, 2, 1])
                est = d.number_input("Preço estimado", min_value=0.0, value=float(item.get("preco_estimado") or 0), step=0.01, key=f"e{item['id']}")
                realp = e.number_input("Preço pago", min_value=0.0, value=float(item.get("preco_unitario") or 0), step=0.01, key=f"p{item['id']}")
                if est != float(item.get("preco_estimado") or 0) or realp != float(item.get("preco_unitario") or 0):
                    update_item(item["id"], preco_estimado=est, preco_unitario=realp)
                    st.rerun()
                if f.button("Excluir", key=f"d{item['id']}"):
                    delete_item(item["id"])
                    st.rerun()
    else:
        st.warning("A lista está vazia.")

    st.divider()
    with st.expander("➕ Adicionar produto", expanded=not bool(current)):
        names = [p["nome"] for p in products]
        selected = st.selectbox("Produto existente", ["— Novo produto —"] + names)
        name = st.text_input("Nome", value="" if selected == "— Novo produto —" else selected)
        p = next((x for x in products if x["nome"] == selected), None)
        cats = sorted(set([x.get("categoria", "Mercearia") for x in products] + ["Mercearia", "Hortifruti", "Carnes", "Bebidas", "Limpeza", "Higiene"]))
        category = st.selectbox("Categoria", cats, index=cats.index(p["categoria"]) if p and p.get("categoria") in cats else 0)
        unit = st.text_input("Unidade", value=p.get("unidade", "un.") if p else "un.")
        default_price = float(p.get("ultimo_preco") or 0) if p else 0.0
        qty = st.number_input("Quantidade", min_value=0.001, value=float(p.get("ultima_quantidade") or 1) if p else 1.0, step=1.0)
        price = st.number_input("Preço estimado", min_value=0.0, value=default_price, step=0.01)
        if st.button("Adicionar à lista", type="primary"):
            if not name.strip():
                st.error("Informe o nome do produto.")
            else:
                add_product(name, category, unit, qty, price)
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        novo_budget = st.number_input("Orçamento / caixa", min_value=0.0, value=budget, step=10.0)
        if st.button("Salvar orçamento"):
            set_budget(novo_budget)
            st.rerun()
    with col2:
        if st.button("Finalizar compra", type="primary", disabled=not bool(current)):
            try:
                finalize_purchase(current, budget)
                st.success("Compra registrada no histórico e lista atual limpa.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao finalizar: {e}")

elif aba == "📦 Produtos":
    st.subheader("Cadastro e histórico de produtos")
    busca = st.text_input("Pesquisar", placeholder="Arroz, leite, sabão...")
    filtrados = [p for p in products if not busca.strip() or busca.lower() in p["nome"].lower()]
    if filtrados:
        df = pd.DataFrame([{
            "Produto": p["nome"], "Categoria": p["categoria"], "Unidade": p["unidade"],
            "Último preço": money(p.get("ultimo_preco")), "Preço médio": money(p.get("preco_medio")),
            "Menor": money(p.get("menor_preco")), "Maior": money(p.get("maior_preco")),
            "Compras": p.get("quantidade_compras", 0),
        } for p in filtrados])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum produto cadastrado.")

elif aba == "📜 Histórico":
    st.subheader("Histórico de compras")
    compras = history()
    if not compras:
        st.info("Nenhuma compra finalizada ainda.")
    for compra in compras:
        data = compra.get("data_compra", "")[:16].replace("T", " ")
        with st.expander(f"{data} · {money(compra.get('valor_real'))} · {compra.get('quantidade_itens', 0)} itens"):
            st.write(f"**Orçamento:** {money(compra.get('orcamento'))}  |  **Estimado:** {money(compra.get('valor_estimado'))}  |  **Saldo:** {money(compra.get('saldo'))}")
            itens = history_items(compra["id"])
            if itens:
                st.dataframe(pd.DataFrame([{
                    "Produto": x["nome_produto"], "Qtd": x["quantidade"], "Un": x["unidade"],
                    "Estimado": money(x.get("preco_estimado")), "Pago": money(x.get("preco_unitario")),
                    "Total": money(x.get("valor_total")), "Confirmado": "Sim" if x.get("confirmado") else "Não",
                } for x in itens]), use_container_width=True, hide_index=True)

elif aba == "📊 Análises":
    st.subheader("Análises")
    compras = history()
    if compras:
        total_real = sum(float(c.get("valor_real") or 0) for c in compras)
        total_est = sum(float(c.get("valor_estimado") or 0) for c in compras)
        x, y, z = st.columns(3)
        x.metric("Compras", len(compras))
        y.metric("Gasto total", money(total_real))
        z.metric("Variação vs. estimado", money(total_real - total_est))
        st.bar_chart(pd.DataFrame({"Real": [float(c.get("valor_real") or 0) for c in compras], "Estimado": [float(c.get("valor_estimado") or 0) for c in compras]}))
    else:
        st.info("Finalize pelo menos uma compra para gerar análises.")

else:
    st.subheader("Configurações")
    st.write("**Banco:** Supabase compartilhado")
    st.write(f"**Projeto:** `{SUPABASE_URL}`")
    st.warning("O acesso atual usa a chave publicável do Supabase. Para um ambiente de produção, recomendamos autenticação e políticas RLS por usuário.")
    if st.button("Recarregar dados"):
        st.rerun()

st.divider()
st.caption("Compra Fácil V4 · Dados salvos no Supabase e compartilhados entre dispositivos.")
