from pathlib import Path
import urllib.request

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/e207deca8b264ae72fe4f8b8a48a9b49e50b9847/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

# Mantém a correção já validada: duplicidade bloqueada sem sumir a lista.
needle = "        st.stop()"
if source.count(needle) < 2:
    raise RuntimeError("Tratamento de duplicidade esperado não foi encontrado.")
source = source.replace(needle, "        return", 2)

alt_add = '''def add_item(name,cat,unit,qty,price,alt_name=None,alt_cat=None,alt_unit=None,alt_price=0):
    existing=db("lista_atual",params={"select":"id,nome_produto"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
        return False
    data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}
    if alt_name and norm(alt_name)!=norm(name):
        data.update({"produto_alternativo":alt_name.strip(),"categoria_alternativa":alt_cat or "Mercearia","unidade_alternativa":alt_unit or "un.","preco_estimado_alternativo":num(alt_price),"produto_escolhido":None})
    try:
        db("lista_atual","POST",data=data)
    except RuntimeError as e:
        if "23505" in str(e):
            st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
            return False
        raise
    clear()
    return True
'''

alt_next = '''def move_item_to_next_list(item_id):
    rows=db("lista_atual",params={"select":"*","id":f"eq.{item_id}"})
    if not rows: return False
    item=rows[0]
    pending=db("lista_proxima",params={"select":"*"})
    same=next((p for p in pending if norm(p.get("nome_produto"))==norm(item.get("nome_produto"))),None)
    if same:
        new_qty=num(same.get("quantidade"))+num(item.get("quantidade"))
        patch={"quantidade":new_qty,"preco_estimado":num(same.get("preco_estimado")) or num(item.get("preco_estimado")),"atualizado_em":now()}
        if not same.get("produto_alternativo") and item.get("produto_alternativo"):
            patch.update({"produto_alternativo":item.get("produto_alternativo"),"categoria_alternativa":item.get("categoria_alternativa"),"unidade_alternativa":item.get("unidade_alternativa"),"preco_estimado_alternativo":num(item.get("preco_estimado_alternativo"))})
        db("lista_proxima","PATCH",params={"id":f"eq.{same['id']}"},data=patch)
    else:
        db("lista_proxima","POST",data={"nome_produto":item.get("nome_produto"),"categoria":item.get("categoria","Mercearia"),"unidade":item.get("unidade","un."),"quantidade":num(item.get("quantidade")),"preco_estimado":num(item.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now(),"produto_alternativo":item.get("produto_alternativo"),"categoria_alternativa":item.get("categoria_alternativa"),"unidade_alternativa":item.get("unidade_alternativa"),"preco_estimado_alternativo":num(item.get("preco_estimado_alternativo")),"produto_escolhido":None})
    db("lista_atual","DELETE",params={"id":f"eq.{item_id}"})
    clear()
    return True

def restore_next_list():
    pending=db("lista_proxima",params={"select":"*","order":"id.asc"})
    if not pending: return 0
    rows=[{"nome_produto":x.get("nome_produto"),"categoria":x.get("categoria","Mercearia"),"unidade":x.get("unidade","un."),"quantidade":num(x.get("quantidade")),"preco_estimado":num(x.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now(),"produto_alternativo":x.get("produto_alternativo"),"categoria_alternativa":x.get("categoria_alternativa"),"unidade_alternativa":x.get("unidade_alternativa"),"preco_estimado_alternativo":num(x.get("preco_estimado_alternativo")),"produto_escolhido":None} for x in pending]
    db("lista_atual","POST",data=rows)
    db("lista_proxima","DELETE",params={"id":"gt.0"})
    clear()
    return len(rows)

'''

alt_dialog = '''@st.dialog("Adicionar produto à lista de compras")
def add_list_dialog(products):
    names=[p.get("nome","") for p in products if p.get("nome")]
    if not names:
        st.info("Cadastre produtos primeiro na aba Produtos.")
        return
    selected=st.selectbox("Produto principal",names,key="dialog_main_product")
    qty=st.number_input("Quantidade",min_value=.001,value=1.,step=1.,format="%.2f",key="dialog_main_qty")
    p=find_product(products,selected)
    use_alt=st.checkbox("Definir produto alternativo",key="dialog_use_alt")
    alt_name=None; alt_p=None
    if use_alt:
        alt_names=[n for n in names if norm(n)!=norm(selected)]
        if alt_names:
            alt_name=st.selectbox("Produto alternativo",alt_names,key="dialog_alt_product")
            alt_p=find_product(products,alt_name)
            st.caption("O valor estimado da lista continuará usando o produto principal.")
        else:
            st.info("Não há outro produto cadastrado para usar como alternativa.")
    if st.button("Adicionar à lista",type="primary",use_container_width=True,key="dialog_add_product") and p:
        ok=add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco")),alt_name,alt_p.get("categoria","Mercearia") if alt_p else None,alt_p.get("unidade","un.") if alt_p else None,num(alt_p.get("ultimo_preco")) if alt_p else 0)
        if ok: st.rerun()
'''

alt_confirm = '''@st.dialog("Confirmar compra do item")
def confirm_dialog(item):
    main=item.get("nome_produto",""); alt=item.get("produto_alternativo")
    qty=num(item.get("quantidade")); estimated=num(item.get("preco_estimado"))
    st.markdown(f"### {main}")
    st.caption(f"Quantidade: {qty:g} {item.get('unidade','un.')}")
    choice=main
    if alt:
        options=[main,alt]; previous=item.get("produto_escolhido")
        choice=st.radio("Qual produto você comprou?",options,index=options.index(previous) if previous in options else 0,horizontal=True,key=f"confirm_choice_{item['id']}")
        st.caption(f"Planejado: {main} · Alternativa: {alt}. O cálculo estimado permanece baseado em {main}.")
    reference=estimated
    if alt and norm(choice)==norm(alt): reference=num(item.get("preco_estimado_alternativo")) or estimated
    price=st.number_input("Preço unitário pago",min_value=0.,value=num(item.get("preco_unitario")) or reference,step=.01,format="%.2f",key=f"confirm_price_{item['id']}_{norm(choice)}")
    variation=price-estimated; variation_pct=(variation/estimated*100) if estimated else None
    c1,c2=st.columns(2)
    with c1: st.metric("Base estimada",money(estimated))
    with c2: st.metric("Variação",money(variation),delta=f"{variation_pct:+.1f}%" if variation_pct is not None else None)
    if alt and norm(choice)==norm(alt): st.info(f"Será registrado como compra de {alt}, mantendo {main} como produto planejado.")
    if estimated:
        if variation > 0: st.warning(f"Preço {money(variation)} acima da base estimada ({variation_pct:+.1f}%).")
        elif variation < 0: st.success(f"Economia de {money(abs(variation))} ({abs(variation_pct):.1f}%) em relação à base estimada.")
        else: st.info("Preço igual ao valor estimado.")
    st.metric("Total do item",money(qty*price))
    a,b=st.columns(2)
    if a.button("Cancelar",use_container_width=True): st.session_state.pop("confirm_item",None); st.rerun()
    if b.button("Confirmar",type="primary",use_container_width=True): edit_item(item["id"],preco_unitario=price,confirmado=True,produto_escolhido=choice); st.session_state.pop("confirm_item",None); st.rerun()

'''

alt_finish = '''def finish(items,budget):
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
        planned=x.get("nome_produto"); alt=x.get("produto_alternativo"); chosen=x.get("produto_escolhido") or planned
        is_alt=bool(alt and norm(chosen)==norm(alt))
        chosen_cat=x.get("categoria_alternativa","Mercearia") if is_alt else x.get("categoria","Mercearia")
        chosen_unit=x.get("unidade_alternativa","un.") if is_alt else x.get("unidade","un.")
        pid=create_product(chosen,chosen_cat,chosen_unit,p or e,q)
        rows.append({"compra_id":c["id"],"produto_id":pid,"nome_produto":chosen,"quantidade":q,"unidade":chosen_unit,"preco_estimado":e,"preco_unitario":p,"valor_total":q*p,"ultimo_preco":e,"variacao_preco":p-e,"confirmado":True,"produto_planejado":planned,"produto_alternativo":alt,"foi_alternativa":is_alt})
    if rows:
        db("itens_compra","POST",data=rows)
        for pid in {x["produto_id"] for x in rows}: product_stats(pid)
    db("lista_atual","DELETE",params={"id":"gt.0"})
    save_budget(0)
'''

inline_old = '''            with st.popover("Adicionar produto à lista de compras",use_container_width=True):
                names=[p.get("nome","") for p in products if p.get("nome")]
                selected=st.selectbox("Produto",names,key="add_product_select")
                qty=st.number_input("Quantidade",min_value=.001,value=1.,step=1.,format="%.2f",key="add_product_qty")
                p=find_product(products,selected)
                if st.button("Adicionar à lista",type="primary",use_container_width=True,key="add_product_submit") and p:
                    add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))); st.rerun()
'''

inline_new = '''            with st.popover("Adicionar produto à lista de compras",use_container_width=True):
                names=[p.get("nome","") for p in products if p.get("nome")]
                selected=st.selectbox("Produto principal",names,key="add_product_select")
                qty=st.number_input("Quantidade",min_value=.001,value=1.,step=1.,format="%.2f",key="add_product_qty")
                p=find_product(products,selected)
                use_alt=st.checkbox("Definir produto alternativo",key="add_use_alt")
                alt_name=None; alt_p=None
                if use_alt:
                    alt_names=[n for n in names if norm(n)!=norm(selected)]
                    if alt_names:
                        alt_name=st.selectbox("Produto alternativo",alt_names,key="add_alt_product")
                        alt_p=find_product(products,alt_name)
                        st.caption("O estimado continuará usando o produto principal.")
                    else:
                        st.info("Não há outro produto cadastrado para usar como alternativa.")
                if st.button("Adicionar à lista",type="primary",use_container_width=True,key="add_product_submit") and p:
                    ok=add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco")),alt_name,alt_p.get("categoria","Mercearia") if alt_p else None,alt_p.get("unidade","un.") if alt_p else None,num(alt_p.get("ultimo_preco")) if alt_p else 0)
                    if ok: st.rerun()
'''

card_old = '''        with a: st.markdown(f'<div class="product-name {"done" if ok else ""}">{item["nome_produto"]}</div><div class="muted">{item.get("categoria","Mercearia")} · {num(item.get("quantidade")):g} {item.get("unidade","un.")}</div>',unsafe_allow_html=True)
'''

card_new = '''        with a:
            _alt=item.get("produto_alternativo"); _chosen=item.get("produto_escolhido")
            _extra=f'<div class="muted">Alternativa: <strong>{_alt}</strong></div>' if _alt else ""
            if ok and _chosen and norm(_chosen)!=norm(item.get("nome_produto")): _extra+=f'<div class="muted">Comprado: <strong>{_chosen}</strong></div>'
            st.markdown(f'<div class="product-name {"done" if ok else ""}">{item["nome_produto"]}</div><div class="muted">{item.get("categoria","Mercearia")} · {num(item.get("quantidade")):g} {item.get("unidade","un.")}</div>{_extra}',unsafe_allow_html=True)
'''

alt_inner = (
    "\nimport re as _alt_re\n"
    "_source, _n = _alt_re.subn(r'def move_item_to_next_list\\(item_id\\):.*?\\ndef add_item', " + repr(alt_next + "def add_item") + ", _source, count=1, flags=_alt_re.S)\n"
    "if _n != 1: raise RuntimeError('Funcoes da proxima lista para alternativas nao foram aplicadas.')\n"
    "_source, _n = _alt_re.subn(r'def add_item\\(name,cat,unit,qty,price\\):.*?\\ndef edit_item', " + repr(alt_add + "\ndef edit_item") + ", _source, count=1, flags=_alt_re.S)\n"
    "if _n != 1: raise RuntimeError('Inclusao de produto alternativo nao foi aplicada.')\n"
    "_source, _n = _alt_re.subn(r'@st\\.dialog\\(\"Adicionar produto à lista de compras\"\\)\\ndef add_list_dialog\\(products\\):.*?(?=\\n@st\\.dialog\\(\"Adicionar novo produto\"\\))', " + repr(alt_dialog.rstrip()) + ", _source, count=1, flags=_alt_re.S)\n"
    "if _n != 1: raise RuntimeError('Dialogo de alternativa nao foi aplicado.')\n"
    "_source, _n = _alt_re.subn(r'@st\\.dialog\\(\"Confirmar compra do item\"\\)\\ndef confirm_dialog\\(item\\):.*?(?=\\n@st\\.dialog\\(\"Excluir histórico\"\\))', " + repr(alt_confirm.rstrip()) + ", _source, count=1, flags=_alt_re.S)\n"
    "if _n != 1: raise RuntimeError('Confirmacao de alternativa nao foi aplicada.')\n"
    "_source, _n = _alt_re.subn(r'def finish\\(items,budget\\):.*?\\ndef delete_history_purchase', " + repr(alt_finish + "\ndef delete_history_purchase") + ", _source, count=1, flags=_alt_re.S)\n"
    "if _n != 1: raise RuntimeError('Finalizacao com alternativa nao foi aplicada.')\n"
    "_inline_old = " + repr(inline_old) + "\n_inline_new = " + repr(inline_new) + "\n"
    "if _inline_old not in _source: raise RuntimeError('Inclusao inline de alternativa nao encontrada.')\n"
    "_source = _source.replace(_inline_old,_inline_new,1)\n"
    "_card_old = " + repr(card_old) + "\n_card_new = " + repr(card_new) + "\n"
    "if _card_old not in _source: raise RuntimeError('Card de produto para alternativa nao encontrado.')\n"
    "_source = _source.replace(_card_old,_card_new,1)\n"
)

# O e207 monta o 687 e o 687 executa o 0074. Inserimos um segundo bridge
# no 687 para que o patch abaixo rode dentro do 0074, quando _source já é
# o app_original final transformado.
e207_exec='exec(compile(source, str(Path(__file__)), "exec"))'
inner_marker='exec(compile(_source,"app_original.py","exec"),globals(),globals())'
outer_marker='exec(compile(_source, str(Path(__file__)), "exec"))'

alt_bridge=(
    "\n_alt_inner_marker = " + repr(inner_marker) + "\n"
    "_alt_inner_patch = " + repr(alt_inner) + "\n"
    "if _alt_inner_marker not in _source: raise RuntimeError('Ponto de execucao do app_original para alternativas nao encontrado.')\n"
    "_source = _source.replace(_alt_inner_marker,_alt_inner_patch+_alt_inner_marker,1)\n"
)

inject=(
    "\n_alt_outer_marker = " + repr(outer_marker) + "\n"
    "_alt_bridge = " + repr(alt_bridge) + "\n"
    "_alt_pos = source.rfind(_alt_outer_marker)\n"
    "if _alt_pos < 0: raise RuntimeError('Execucao do 687 para alternativas nao encontrada.')\n"
    "source = source[:_alt_pos] + _alt_bridge + source[_alt_pos:]\n\n"
)

pos=source.rfind(e207_exec)
if pos<0:
    raise RuntimeError("Execução do wrapper-base não encontrada.")
source=source[:pos]+inject+source[pos:]

exec(compile(source, str(Path(__file__)), "exec"))
