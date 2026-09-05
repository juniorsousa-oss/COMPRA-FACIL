import os
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Compra Fácil", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", "https://cuixazpxkvniqldmmnth.supabase.co")).rstrip("/")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))

st.markdown("""
<style>
#MainMenu,footer,header{visibility:hidden}
.block-container{max-width:1150px;padding:1rem .9rem 5rem}
.brand{display:flex;align-items:center;gap:12px;margin:4px 0 2px}.brand-icon{width:48px;height:48px;border-radius:14px;background:#111827;display:flex;align-items:center;justify-content:center;font-size:25px}.brand-title{font-size:2rem;font-weight:800;color:#111827;line-height:1}.subtitle{margin:0 0 18px 60px;color:#6b7280;font-size:.88rem}
.card{border:1px solid #e5e7eb;border-radius:16px;padding:14px 16px;background:white;box-shadow:0 1px 2px rgba(0,0,0,.03);margin-bottom:10px}.label{font-size:.78rem;color:#6b7280}.value{font-size:1.35rem;font-weight:750;color:#111827;margin-top:3px}.product-name{font-size:1.05rem;font-weight:750;color:#111827}.muted{font-size:.8rem;color:#6b7280}.done{text-decoration:line-through;color:#6b7280}.pill{display:inline-block;padding:5px 9px;border-radius:999px;font-size:.72rem;font-weight:700;background:#ecfdf5;color:#047857}.empty{border:1px dashed #d1d5db;border-radius:16px;padding:32px 16px;text-align:center;color:#6b7280;background:#fafafa;margin:10px 0}
.stButton>button,.stDownloadButton>button{border-radius:11px;min-height:42px}.stTextInput input,.stNumberInput input{border-radius:10px}div[data-testid="stMetric"]{border:1px solid #e5e7eb;border-radius:15px;padding:12px}
@media(max-width:700px){.block-container{padding:.7rem .65rem 4rem}.brand-title{font-size:1.65rem}.brand-icon{width:44px;height:44px;font-size:22px}.subtitle{margin-left:56px;font-size:.78rem}.card{padding:12px}.value{font-size:1.1rem}}
</style>
""", unsafe_allow_html=True)

if not SUPABASE_KEY:
    st.error("Supabase não configurado. No Streamlit Cloud, abra Settings → Secrets e informe SUPABASE_URL e SUPABASE_KEY.")
    st.stop()

HEADERS={"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json"}

def db(table, method="GET", params=None, data=None):
    r=requests.request(method,f"{SUPABASE_URL}/rest/v1/{table}",headers=HEADERS,params=params,json=data,timeout=20)
    if not r.ok: raise RuntimeError(f"Supabase {r.status_code}: {r.text[:600]}")
    return r.json() if r.text else []

def now(): return datetime.now(timezone.utc).isoformat()
def n(v):
    try:return float(v or 0)
    except:return 0.0
def money(v): return f"R$ {n(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")

def clear():
    for fn in (get_products,get_current,get_budget,get_history): fn.clear()

@st.cache_data(ttl=15,show_spinner=False)
def get_products(): return db("produtos",params={"select":"*","order":"nome.asc"})
@st.cache_data(ttl=4,show_spinner=False)
def get_current(): return db("lista_atual",params={"select":"*","order":"categoria.asc,nome_produto.asc"})
@st.cache_data(ttl=10,show_spinner=False)
def get_budget():
    r=db("estado_app",params={"select":"orcamento","id":"eq.1"})
    return n(r[0].get("orcamento")) if r else 0
@st.cache_data(ttl=15,show_spinner=False)
def get_history(): return db("compras",params={"select":"*","order":"data_compra.desc"})

def add_item(name,cat,unit,qty,price):
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":n(qty),"preco_estimado":n(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()});clear()
def edit_item(i,**data): data["atualizado_em"]=now();db("lista_atual","PATCH",params={"id":f"eq.{i}"},data=data);clear()
def remove_item(i): db("lista_atual","DELETE",params={"id":f"eq.{i}"});clear()
def save_budget(v):
    data={"orcamento":n(v),"atualizado_em":now()};r=db("estado_app",params={"select":"id","id":"eq.1"})
    if r: db("estado_app","PATCH",params={"id":"eq.1"},data=data)
    else: db("estado_app","POST",data={"id":1,**data})
    clear()
def save_product(name,cat,unit,price,qty):
    r=db("produtos",params={"select":"*","nome":f"ilike.{name.strip()}"})
    if r:
        p=r[0];old=n(p.get("ultimo_preco"));prices=[x for x in [old,n(price)] if x>0]
        db("produtos","PATCH",params={"id":f"eq.{p['id']}"},data={"categoria":cat,"unidade":unit,"ultimo_preco":n(price),"preco_medio":sum(prices)/len(prices) if prices else 0,"menor_preco":min(prices) if prices else 0,"maior_preco":max(prices) if prices else 0,"ultima_quantidade":n(qty),"quantidade_compras":int(p.get("quantidade_compras") or 0)+1,"atualizado_em":now()})
    else:
        db("produtos","POST",data={"nome":name.strip(),"categoria":cat,"unidade":unit,"ultimo_preco":n(price),"preco_medio":n(price),"menor_preco":n(price),"maior_preco":n(price),"ultima_quantidade":n(qty),"quantidade_compras":1,"atualizado_em":now()})
def finish(items,budget):
    est=sum(n(x.get("quantidade"))*n(x.get("preco_estimado")) for x in items);real=sum(n(x.get("quantidade"))*n(x.get("preco_unitario")) for x in items if x.get("confirmado"))
    c=db("compras","POST",data={"orcamento":n(budget),"valor_estimado":est,"valor_real":real,"saldo":n(budget)-real,"quantidade_itens":len(items),"data_compra":now()})[0]
    rows=[]
    for x in items:
        q=n(x.get("quantidade"));e=n(x.get("preco_estimado"));p=n(x.get("preco_unitario"));rows.append({"compra_id":c["id"],"produto_id":None,"nome_produto":x["nome_produto"],"quantidade":q,"unidade":x["unidade"],"preco_estimado":e,"preco_unitario":p,"valor_total":q*p,"ultimo_preco":e,"variacao_preco":p-e,"confirmado":bool(x.get("confirmado"))});save_product(x["nome_produto"],x.get("categoria","Mercearia"),x.get("unidade","un."),p or e,q)
    if rows: db("itens_compra","POST",data=rows)
    db("lista_atual","DELETE",params={"id":"gt.0"});clear()

@st.dialog("Confirmar compra do item")
def confirm_dialog(item):
    st.markdown(f"### {item['nome_produto']}")
    st.caption(f"Quantidade: {n(item.get('quantidade')):g} {item.get('unidade','un.')}")
    price=st.number_input("Preço unitário pago",min_value=0.0,value=n(item.get("preco_unitario")) or n(item.get("preco_estimado")),step=.01,format="%.2f")
    st.metric("Total do item",money(n(item.get("quantidade"))*price))
    a,b=st.columns(2)
    if a.button("Cancelar",use_container_width=True): st.rerun()
    if b.button("Confirmar",type="primary",use_container_width=True): edit_item(item["id"],preco_unitario=price,confirmado=True);st.rerun()

try:
    products=get_products();current=get_current();budget=get_budget();history=get_history()
except Exception as e:
    st.error(f"Não consegui acessar o banco de dados.\n\n{e}");st.stop()

st.markdown('<div class="brand"><div class="brand-icon">🛒</div><div class="brand-title">Compra Fácil</div></div>',unsafe_allow_html=True)
st.markdown('<div class="subtitle">Lista de compras, preços e histórico em um só lugar.</div>',unsafe_allow_html=True)

estimated=sum(n(x.get("quantidade"))*n(x.get("preco_estimado")) for x in current)
real=sum(n(x.get("quantidade"))*n(x.get("preco_unitario")) for x in current if x.get("confirmado"))
done=sum(1 for x in current if x.get("confirmado"))

cols=st.columns(4)
for col,label,value in zip(cols,["Orçamento","Estimado","Real confirmado","Saldo"],[money(budget),money(estimated),money(real),money(budget-real)]):
    with col: st.markdown(f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>',unsafe_allow_html=True)
if budget>0: st.progress(min(real/budget,1),text=f"Consumo confirmado: {real/budget:.0%}")
st.caption(f"Lista atual: {done} de {len(current)} itens confirmados")

buy,prod,hist,ana,config=st.tabs(["🛒 Compra","📦 Produtos","📜 Histórico","📊 Análises","⚙️ Configurações"])

with buy:
    st.subheader("Lista de compras")
    if not current:
        st.markdown('<div class="empty"><strong>Sua lista está vazia.</strong><br>Adicione um produto abaixo.</div>',unsafe_allow_html=True)
    for item in current:
        ok=bool(item.get("confirmado"));total=n(item.get("quantidade"))*n(item.get("preco_estimado"))
        st.markdown('<div class="card">',unsafe_allow_html=True)
        a,b=st.columns([4,1])
        with a:
            cls="product-name done" if ok else "product-name";st.markdown(f'<div class="{cls}">{item["nome_produto"]}</div>',unsafe_allow_html=True);st.markdown(f'<div class="muted">{item.get("categoria","Mercearia")} · {n(item.get("quantidade")):g} {item.get("unidade","un.")}</div>',unsafe_allow_html=True)
        with b:
            if ok: st.markdown('<span class="pill">✓ Confirmado</span>',unsafe_allow_html=True)
            else: st.markdown(f'<div style="text-align:right;font-weight:700">{money(total)}</div>',unsafe_allow_html=True)
        c1,c2,c3=st.columns([1.2,1.3,1])
        with c1:
            q=st.number_input("Qtd",min_value=.001,value=n(item.get("quantidade")) or 1.,step=1.,key=f"q{item['id']}",disabled=ok)
            if q!=n(item.get("quantidade")) and not ok: edit_item(item["id"],quantidade=q);st.rerun()
        with c2:
            st.caption("Preço estimado");st.write(money(item.get("preco_estimado")))
        with c3:
            if not ok:
                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True): confirm_dialog(item)
            else: st.caption("Preço pago");st.write(money(item.get("preco_unitario")))
        d1,d2=st.columns([3,1])
        with d1: st.caption(f"Total pago: {money(n(item.get('quantidade'))*n(item.get('preco_unitario')))}" if ok else "Aguardando confirmação do preço")
        with d2:
            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]);st.rerun()
        st.markdown('</div>',unsafe_allow_html=True)

    st.divider();st.markdown("### Adicionar produto")
    names=[p.get("nome","") for p in products];selected=st.selectbox("Produto existente",["+ Novo produto"]+names)
    existing=next((p for p in products if p.get("nome")==selected),None)
    cats=sorted(set(["Mercearia","Hortifruti","Carnes","Bebidas","Limpeza","Higiene","Padaria"]+[p.get("categoria","Mercearia") for p in products]))
    with st.form("add"):
        name=st.text_input("Nome",value=existing.get("nome","") if existing else "")
        cat=st.selectbox("Categoria",cats,index=cats.index(existing.get("categoria")) if existing and existing.get("categoria") in cats else 0)
        a,b,c=st.columns(3)
        unit=a.text_input("Unidade",value=existing.get("unidade","un.") if existing else "un.")
        qty=b.number_input("Quantidade",min_value=.001,value=n(existing.get("ultima_quantidade")) or 1. if existing else 1.,step=1.)
        price=c.number_input("Preço estimado",min_value=0.,value=n(existing.get("ultimo_preco")) if existing else 0.,step=.01,format="%.2f")
        if st.form_submit_button("Adicionar à lista",type="primary",use_container_width=True):
            if not name.strip(): st.error("Informe o nome do produto.")
            else: add_item(name,cat,unit,qty,price);st.rerun()
    st.divider();st.markdown("### Fechamento")
    new_budget=st.number_input("Orçamento / dinheiro disponível",min_value=0.,value=budget,step=10.,format="%.2f")
    a,b=st.columns(2)
    if a.button("Salvar orçamento",use_container_width=True): save_budget(new_budget);st.rerun()
    if b.button("Finalizar e salvar compra",type="primary",disabled=not bool(current),use_container_width=True):
        try: finish(current,budget);st.success("Compra salva no histórico.");st.rerun()
        except Exception as e: st.error(f"Erro ao finalizar: {e}")

with prod:
    st.subheader("Produtos")
    search=st.text_input("Pesquisar produto",placeholder="Arroz, leite, sabão...")
    rows=[p for p in products if not search.strip() or search.lower() in p.get("nome","").lower()]
    if rows:
        st.dataframe(pd.DataFrame([{"Produto":p.get("nome"),"Categoria":p.get("categoria"),"Unidade":p.get("unidade"),"Último":money(p.get("ultimo_preco")),"Médio":money(p.get("preco_medio")),"Menor":money(p.get("menor_preco")),"Maior":money(p.get("maior_preco")),"Compras":p.get("quantidade_compras",0)} for p in rows]),use_container_width=True,hide_index=True)
    else: st.info("Nenhum produto encontrado.")

with hist:
    st.subheader("Histórico de compras")
    if not history: st.markdown('<div class="empty">Nenhuma compra finalizada ainda.</div>',unsafe_allow_html=True)
    for purchase in history:
        date=str(purchase.get("data_compra",""))[:16].replace("T"," ")
        with st.expander(f"{date} · {money(purchase.get('valor_real'))} · {purchase.get('quantidade_itens',0)} itens"):
            a,b,c,d=st.columns(4);a.metric("Orçamento",money(purchase.get("orcamento")));b.metric("Estimado",money(purchase.get("valor_estimado")));c.metric("Real",money(purchase.get("valor_real")));d.metric("Saldo",money(purchase.get("saldo")))
            items=db("itens_compra",params={"select":"*","compra_id":f"eq.{purchase['id']}","order":"id.asc"})
            if items: st.dataframe(pd.DataFrame([{"Produto":x.get("nome_produto"),"Qtd":n(x.get("quantidade")),"Un":x.get("unidade"),"Estimado":money(x.get("preco_estimado")),"Pago":money(x.get("preco_unitario")),"Total":money(x.get("valor_total")),"Confirmado":"Sim" if x.get("confirmado") else "Não"} for x in items]),use_container_width=True,hide_index=True)

with ana:
    st.subheader("Análises")
    if history:
        total=sum(n(x.get("valor_real")) for x in history);est=sum(n(x.get("valor_estimado")) for x in history)
        a,b,c=st.columns(3);a.metric("Compras",len(history));b.metric("Gasto acumulado",money(total));c.metric("Diferença",money(total-est))
        chart=pd.DataFrame({"Estimado":[n(x.get("valor_estimado")) for x in history],"Real":[n(x.get("valor_real")) for x in history]})
        st.bar_chart(chart)
    else: st.markdown('<div class="empty">Finalize uma compra para gerar análises.</div>',unsafe_allow_html=True)

with config:
    st.subheader("Configurações")
    st.success("Banco de dados conectado")
    st.write(f"**Supabase:** `{SUPABASE_URL}`")
    st.write("**Banco:** PostgreSQL / Supabase")
    st.write("**Lista:** compartilhada entre dispositivos")
    if st.button("Atualizar dados agora",use_container_width=True): clear();st.rerun()
    st.caption("A chave do Supabase deve permanecer no Secrets do Streamlit Cloud, nunca no código do GitHub.")
