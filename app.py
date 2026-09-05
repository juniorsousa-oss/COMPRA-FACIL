from pathlib import Path
import re

_original = Path(__file__).with_name("app_original.py")
_source = _original.read_text(encoding="utf-8")

# Estatísticas: ao excluir histórico, recalcula também produtos que ficaram sem histórico.
_source = re.sub(r"def delete_history_purchase\(pid\):.*?\ndef parse_history", '''def delete_history_purchase(pid):
    db("itens_compra","DELETE",params={"compra_id":f"eq.{pid}"})
    db("compras","DELETE",params={"id":f"eq.{pid}"})
    rebuild_product_stats(get_products())
    clear()
def parse_history''', _source, count=1, flags=re.S)

# Limpa decisões antigas antes de uma nova importação de histórico e registra contagens.
_source = _source.replace(
'''def stage_history(uploaded,products):
    rows=parse_history(uploaded); exact=[]; unmatched=[]
''',
'''def stage_history(uploaded,products):
    for k in list(st.session_state.keys()):
        if str(k).startswith(("hist_action_","hist_dest_","hist_cat_","hist_unit_")):
            st.session_state.pop(k,None)
    rows=parse_history(uploaded); exact=[]; unmatched=[]
''',1)
_source = _source.replace(
'''    st.session_state["pending_history"]={"exact":exact,"unmatched":unmatched}
''',
'''    st.session_state["pending_history"]={"exact":exact,"unmatched":unmatched,"source_count":len(rows),"consolidated_count":len(exact)+len(unmatched)}
''',1)

# Finalização: exige preços confirmados e zera o orçamento depois da compra.
_source = re.sub(r"def finish\(items,budget\):.*?\ndef delete_history_purchase", '''def finish(items,budget):
    if num(budget)<=0: raise RuntimeError("Informe o orçamento da compra antes de finalizar.")
    if not items: raise RuntimeError("Adicione pelo menos um item antes de finalizar.")
    if any(not x.get("confirmado") for x in items): raise RuntimeError("Confirme o preço de todos os itens antes de finalizar.")
    est=sum(num(x.get("quantidade"))*num(x.get("preco_estimado")) for x in items)
    real=sum(num(x.get("quantidade"))*num(x.get("preco_unitario")) for x in items)
    created=db("compras","POST",data={"orcamento":num(budget),"valor_estimado":est,"valor_real":real,"saldo":num(budget)-real,"quantidade_itens":len(items),"data_compra":now()})
    if not created: raise RuntimeError("Não foi possível registrar a compra.")
    c=created[0]; rows=[]
    for x in items:
        q=num(x.get("quantidade")); e=num(x.get("preco_estimado")); p=num(x.get("preco_unitario"))
        pid=create_product(x["nome_produto"],x.get("categoria","Mercearia"),x.get("unidade","un."),p or e,q)
        rows.append({"compra_id":c["id"],"produto_id":pid,"nome_produto":x["nome_produto"],"quantidade":q,"unidade":x.get("unidade","un."),"preco_estimado":e,"preco_unitario":p,"valor_total":q*p,"ultimo_preco":e,"variacao_preco":p-e,"confirmado":True})
    if rows:
        db("itens_compra","POST",data=rows)
        for pid in {x["produto_id"] for x in rows}: product_stats(pid)
    db("lista_atual","DELETE",params={"id":"gt.0"})
    save_budget(0)
def delete_history_purchase''', _source, count=1, flags=re.S)

# Orçamento inicial.
_insert='''@st.dialog("Definir orçamento da compra")
def budget_dialog(action):
    st.markdown("### Nova compra")
    st.caption("Informe quanto você pretende gastar. O valor ficará vinculado à compra até ela ser finalizada.")
    value=st.number_input("Orçamento disponível (R$)",min_value=0.01,value=0.01,step=10.0,format="%.2f",key="new_purchase_budget")
    a,b=st.columns(2)
    if a.button("Cancelar",use_container_width=True): st.rerun()
    if b.button("Iniciar compra",type="primary",use_container_width=True):
        save_budget(value)
        st.session_state["open_add_after_budget" if action=="add" else "open_standard_after_budget"]=True
        st.rerun()

'''
_source=_source.replace('@st.dialog("Adicionar produto à lista de compras")\ndef add_list_dialog',_insert+'@st.dialog("Adicionar produto à lista de compras")\ndef add_list_dialog',1)

# Fluxo principal da compra. A alteração do item usa popover, evitando conflito com st.dialog.
_old=re.search(r"with buy:\n.*?(?=with prod:\n)",_source,flags=re.S)
_new='''with buy:
    st.subheader("Lista de compras")
    a,b=st.columns(2)
    with a:
        if not current:
            if st.button("Adicionar produto à lista de compras",type="primary",use_container_width=True,key="open_add_list"):
                budget_dialog("add")
        else:
            with st.popover("Adicionar produto à lista de compras",use_container_width=True):
                names=[p.get("nome","") for p in products if p.get("nome")]
                selected=st.selectbox("Produto",names,key="add_product_select")
                qty=st.number_input("Quantidade",min_value=.001,value=1.,step=1.,format="%.2f",key="add_product_qty")
                p=find_product(products,selected)
                if st.button("Adicionar à lista",type="primary",use_container_width=True,key="add_product_submit") and p:
                    add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))); st.rerun()
    with b:
        if st.button("Importar lista padrão",use_container_width=True,key="import_standard"):
            if not current:
                budget_dialog("standard")
            else:
                rec={}; qs={}
                for hp in history:
                    seen=set()
                    for x in db("itens_compra",params={"select":"nome_produto,quantidade","compra_id":f"eq.{hp['id']}"}):
                        k=norm(x.get("nome_produto"))
                        if k and k not in seen: seen.add(k); rec[k]=rec.get(k,0)+1; qs.setdefault(k,[]).append(num(x.get("quantidade")))
                by={norm(p.get("nome")):p for p in products}; added=0
                for k,cnt in rec.items():
                    if cnt>=2 and k in by and not any(norm(x.get("nome_produto"))==k for x in current):
                        p=by[k]; add_item(p["nome"],p.get("categoria","Mercearia"),p.get("unidade","un."),round(sum(qs[k])/len(qs[k]),2),num(p.get("ultimo_preco"))); added+=1
                st.success(f"{added} produtos recorrentes adicionados."); st.rerun()
    if st.session_state.pop("open_add_after_budget",False): add_list_dialog(products)
    if st.session_state.pop("open_standard_after_budget",False):
        rec={}; qs={}
        for hp in history:
            seen=set()
            for x in db("itens_compra",params={"select":"nome_produto,quantidade","compra_id":f"eq.{hp['id']}"}):
                k=norm(x.get("nome_produto"))
                if k and k not in seen: seen.add(k); rec[k]=rec.get(k,0)+1; qs.setdefault(k,[]).append(num(x.get("quantidade")))
        by={norm(p.get("nome")):p for p in products}; added=0
        for k,cnt in rec.items():
            if cnt>=2 and k in by and not any(norm(x.get("nome_produto"))==k for x in current):
                p=by[k]; add_item(p["nome"],p.get("categoria","Mercearia"),p.get("unidade","un."),round(sum(qs[k])/len(qs[k]),2),num(p.get("ultimo_preco"))); added+=1
        if added: st.success(f"{added} produtos recorrentes adicionados."); st.rerun()
        else: st.info("Não há produtos recorrentes suficientes para montar a lista padrão.")
    if not current: st.markdown('<div class="empty"><strong>Sua lista está vazia.</strong><br>Ao iniciar uma nova compra, o sistema solicitará o orçamento antes do primeiro item.</div>',unsafe_allow_html=True)
    for item in current:
        ok=bool(item.get("confirmado")); total=num(item.get("quantidade"))*num(item.get("preco_estimado"))
        st.markdown('<div class="card">',unsafe_allow_html=True); a,b=st.columns([4,1])
        with a: st.markdown(f'<div class="product-name {"done" if ok else ""}">{item["nome_produto"]}</div><div class="muted">{item.get("categoria","Mercearia")} · {num(item.get("quantidade")):g} {item.get("unidade","un.")}</div>',unsafe_allow_html=True)
        with b: st.markdown('<span class="pill">✓ Confirmado</span>' if ok else f'<div style="text-align:right;font-weight:700">{money(total)}</div>',unsafe_allow_html=True)
        c1,c2,c3=st.columns([1.2,1.3,1])
        with c1:
            q=st.number_input("Qtd",min_value=.001,value=num(item.get("quantidade")) or 1.,step=1.,key=f"q{item['id']}",disabled=ok)
            if q!=num(item.get("quantidade")) and not ok: edit_item(item["id"],quantidade=q); st.rerun()
        with c2: st.caption("Preço estimado"); st.write(money(item.get("preco_estimado")))
        with c3:
            if not ok:
                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True): st.session_state["confirm_item"]=item; st.rerun()
            else: st.caption("Preço pago"); st.write(money(item.get("preco_unitario")))
        d1,d2=st.columns([3,1])
        with d1: st.caption(f"Total pago: {money(num(item.get('quantidade'))*num(item.get('preco_unitario')))}" if ok else "Aguardando confirmação do preço")
        with d2:
            with st.popover("Alterar",use_container_width=True):
                names=[p.get("nome","") for p in products if p.get("nome")]; current_name=item.get("nome_produto",""); idx=names.index(current_name) if current_name in names else 0
                edit_name=st.selectbox("Produto",names,index=idx,key=f"edit_product_{item['id']}")
                edit_qty=st.number_input("Quantidade",min_value=.001,value=num(item.get("quantidade")) or 1.,step=1.,format="%.2f",key=f"edit_qty_{item['id']}")
                if st.button("Salvar alteração",type="primary",use_container_width=True,key=f"edit_save_{item['id']}"):
                    p=find_product(products,edit_name)
                    if p:
                        edit_item(item["id"],nome_produto=edit_name,categoria=p.get("categoria","Mercearia"),unidade=p.get("unidade","un."),quantidade=edit_qty,preco_estimado=num(p.get("ultimo_preco")),preco_unitario=0,confirmado=False); st.rerun()
        if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()
        st.markdown('</div>',unsafe_allow_html=True)
    if current:
        st.divider(); a,b=st.columns([1,2])
        with a: st.caption(f"Compra em andamento · Orçamento: {money(budget)} · Confirmados: {sum(bool(x.get('confirmado')) for x in current)}/{len(current)}")
        with b:
            if st.button("Finalizar compra",type="primary",disabled=not all(bool(x.get("confirmado")) for x in current),use_container_width=True):
                try: finish(current,budget); st.rerun()
                except Exception as e: st.error(f"Erro ao finalizar: {e}")
'''
if not _old: raise RuntimeError("Bloco da compra não encontrado")
_source=_source[:_old.start()]+_new+_source[_old.end():]

# Correção rápida do orçamento enquanto a compra está em andamento.
marker='buy,prod,hist,ana,config=st.tabs(["🛒 Compra","📦 Produtos","📜 Histórico","📊 Análises","⚙️ Configurações"])'
_budget='''buy,prod,hist,ana,config=st.tabs(["🛒 Compra","📦 Produtos","📜 Histórico","📊 Análises","⚙️ Configurações"])
if budget>0:
    with st.popover("Corrigir orçamento"):
        st.caption("Corrija o valor informado no início da compra.")
        new_budget=st.number_input("Novo orçamento (R$)",min_value=0.01,value=float(budget),step=10.0,format="%.2f",key="budget_edit_value")
        if st.button("Salvar novo orçamento",type="primary",use_container_width=True,key="save_budget_edit"):
            save_budget(new_budget); st.rerun()
'''
_source=_source.replace(marker,_budget,1)

# Recalcula produtos sem histórico quando necessário.
_old=re.search(r"def rebuild_product_stats\(products\):.*?\ndef find_product",_source,flags=re.S)
if _old:
    _new='''def rebuild_product_stats(products):
    items=db("itens_compra",params={"select":"produto_id,compra_id,preco_unitario,quantidade,criado_em"}); grouped={}
    for x in items:
        if x.get("produto_id") is not None: grouped.setdefault(str(x["produto_id"]),[]).append(x)
    updated=0
    for p in products:
        rows=grouped.get(str(p.get("id")),[])
        if not rows: continue
        valid=[x for x in rows if num(x.get("preco_unitario"))>0]; prices=[num(x.get("preco_unitario")) for x in valid]; latest=sorted(rows,key=lambda x:str(x.get("criado_em","")))[-1]
        db("produtos","PATCH",params={"id":f"eq.{p['id']}"},data={"ultimo_preco":num(latest.get("preco_unitario")),"preco_medio":sum(prices)/len(prices) if prices else 0,"menor_preco":min(prices) if prices else 0,"maior_preco":max(prices) if prices else 0,"ultima_quantidade":num(latest.get("quantidade")) or 1,"quantidade_compras":len({str(x.get("compra_id")) for x in rows}),"atualizado_em":now()}); updated+=1
    clear(); return updated
def find_product'''
    _source=_source[:_old.start()]+_new+_source[_old.end():]

compile(_source,"app_original.py","exec")
exec(compile(_source,"app_original.py","exec"),globals(),globals())
