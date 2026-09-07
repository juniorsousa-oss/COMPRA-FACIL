from pathlib import Path
import re
import urllib.request

BASE="https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/0074e6f1fe2b4bfdee87793c6bff1fec391d35cc/app.py"
_source=urllib.request.urlopen(BASE,timeout=10).read().decode("utf-8")

# O app-base carrega app_original.py em uma segunda camada. Todas as correções
# abaixo são injetadas nessa segunda camada, que é o código realmente executado.
anchor='''_source = _original.read_text(encoding="utf-8")'''
patch='''_source = _original.read_text(encoding="utf-8")

# Bloqueia duplicidade diretamente no banco antes de inserir.
_source = re.sub(r'def add_item\\(name,cat,unit,qty,price\\):.*?\\ndef edit_item', '''def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto **{name.strip()}** já está nesta lista. Altere a quantidade no item existente.")
        return False
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()
    return True

def edit_item''', _source, count=1, flags=re.S)

# Desconfirmar item já confirmado.
_old_confirm='''        with d1:
            st.button("Confirmado",disabled=True,use_container_width=True,key=f"c_done_{item['id']}") if ok else None
            if not ok and st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True): st.session_state["confirm_item"]=item; st.rerun()
'''
_new_confirm='''        with d1:
            if ok:
                if st.button("Desconfirmar",use_container_width=True,key=f"unconfirm_{item['id']}"):
                    edit_item(item["id"],confirmado=False)
                    st.rerun()
            else:
                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True):
                    st.session_state["confirm_item"]=item
                    st.rerun()
'''
_source=_source.replace(_old_confirm,_new_confirm,1)

# Quantidade pode ser corrigida mesmo depois da confirmação.
_source=_source.replace('q=st.number_input("Qtd",min_value=.001,value=num(item.get("quantidade")) or 1.,step=1.,key=f"q{item[\'id\']}",disabled=ok)','q=st.number_input("Qtd",min_value=.001,value=num(item.get("quantidade")) or 1.,step=1.,key=f"q{item[\'id\']}",disabled=False)\n            if q!=num(item.get("quantidade")):\n                edit_item(item["id"],quantidade=q,confirmado=ok)\n                st.rerun()',1)

# Funções da próxima lista, dentro do código realmente executado.
helpers='''def move_item_to_next_list(item_id):
    rows=db("lista_atual",params={"select":"*","id":f"eq.{item_id}"})
    if not rows: return False
    item=rows[0]
    pending=db("lista_proxima",params={"select":"*"})
    same=next((p for p in pending if norm(p.get("nome_produto"))==norm(item.get("nome_produto"))),None)
    if same:
        new_qty=num(same.get("quantidade"))+num(item.get("quantidade"))
        db("lista_proxima","PATCH",params={"id":f"eq.{same['id']}"},data={"quantidade":new_qty,"preco_estimado":num(same.get("preco_estimado")) or num(item.get("preco_estimado")),"atualizado_em":now()})
    else:
        db("lista_proxima","POST",data={"nome_produto":item.get("nome_produto"),"categoria":item.get("categoria","Mercearia"),"unidade":item.get("unidade","un."),"quantidade":num(item.get("quantidade")),"preco_estimado":num(item.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now()})
    db("lista_atual","DELETE",params={"id":f"eq.{item_id}"})
    clear()
    return True

def restore_next_list():
    pending=db("lista_proxima",params={"select":"*","order":"id.asc"})
    if not pending: return 0
    rows=[{"nome_produto":x.get("nome_produto"),"categoria":x.get("categoria","Mercearia"),"unidade":x.get("unidade","un."),"quantidade":num(x.get("quantidade")),"preco_estimado":num(x.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now()} for x in pending]
    db("lista_atual","POST",data=rows)
    db("lista_proxima","DELETE",params={"id":"gt.0"})
    clear()
    return len(rows)
'''
_source=_source.replace("def add_item(name,cat,unit,qty,price):",helpers+"def add_item(name,cat,unit,qty,price):",1)

# Orçamento para iniciar a próxima compra.
_source=_source.replace('st.session_state["open_add_after_budget" if action=="add" else "open_standard_after_budget"]=True','st.session_state["open_add_after_budget" if action=="add" else ("open_next_after_budget" if action=="next" else "open_standard_after_budget")]=True',1)
_source=_source.replace('    if st.session_state.pop("open_add_after_budget",False): add_list_dialog(products)','    if st.session_state.pop("open_next_after_budget",False):\n        restore_next_list()\n        st.rerun()\n    if st.session_state.pop("open_add_after_budget",False): add_list_dialog(products)',1)

# Lista pendente aparece quando a lista atual está vazia.
old_empty='''    if not current: st.markdown('<div class="empty"><strong>Sua lista está vazia.</strong><br>Ao iniciar uma nova compra, o sistema solicitará o orçamento antes do primeiro item.</div>',unsafe_allow_html=True)'''
new_empty='''    if not current:
        _pending_next=db("lista_proxima",params={"select":"id,nome_produto,quantidade","order":"id.asc"})
        if _pending_next:
            st.info(f"Há {len(_pending_next)} item(ns) guardado(s) para a próxima lista.")
            if st.button("Iniciar próxima compra",type="primary",use_container_width=True,key="start_next_purchase"):
                budget_dialog("next")
        else:
            st.markdown('<div class="empty"><strong>Sua lista está vazia.</strong><br>Ao iniciar uma nova compra, o sistema solicitará o orçamento antes do primeiro item.</div>',unsafe_allow_html=True)'''
_source=_source.replace(old_empty,new_empty,1)

# Quarta ação no card: Próxima lista.
_source=_source.replace('d1,d2,d3=st.columns(3)','d1,d2,d3,d4=st.columns(4)',1)
old_d3='''        with d3:
            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()
'''
new_d3='''        with d3:
            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()
        with d4:
            if not ok:
                if st.button("Próxima lista",key=f"next_{item['id']}",use_container_width=True,help="Guarda este item para a próxima compra."):
                    if move_item_to_next_list(item["id"]):
                        st.toast("Item guardado para a próxima lista.")
                        st.rerun()
            else:
                st.button("Próxima lista",disabled=True,key=f"next_done_{item['id']}",use_container_width=True)
'''
_source=_source.replace(old_d3,new_d3,1)

# O botão de inclusão não faz rerun quando add_item recusou duplicidade.
old_add='''                    add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))); st.rerun()'''
new_add='''                    if add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))):
                        st.rerun()'''
_source=_source.replace(old_add,new_add,1)

if anchor not in _source:
    pass
'''
# The above patch itself is injected into base source, then the base source executes it.
_source = _source.replace(anchor, patch, 1)

exec(compile(_source,str(Path(__file__)),"exec"))