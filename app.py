from pathlib import Path
import re
import urllib.request

_BASE_URL = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/0074e6f1fe2b4bfdee87793c6bff1fec391d35cc/app.py"
_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")

# Desconfirmar item já confirmado.
_old = '''        with d1:\n            st.button("Confirmado",disabled=True,use_container_width=True,key=f"c_done_{item['id']}") if ok else None\n            if not ok and st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True): st.session_state["confirm_item"]=item; st.rerun()\n'''
_new = '''        with d1:\n            if ok:\n                if st.button("Desconfirmar",use_container_width=True,key=f"unconfirm_{item['id']}"):\n                    edit_item(item["id"],confirmado=False)\n                    st.rerun()\n            else:\n                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True):\n                    st.session_state["confirm_item"]=item\n                    st.rerun()\n'''
if _old in _source:
    _source = _source.replace(_old, _new, 1)

# Impede duplicação na lista atual.
_old_add = '''def add_item(name,cat,unit,qty,price):\n    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()\n'''
_new_add = '''def add_item(name,cat,unit,qty,price):\n    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})\n    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):\n        raise RuntimeError(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")\n    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()\n'''
if _old_add in _source:
    _source = _source.replace(_old_add, _new_add, 1)

# Funções da próxima lista.
_next_helpers = '''def move_item_to_next_list(item_id):\n    rows=db("lista_atual",params={"select":"*","id":f"eq.{item_id}"})\n    if not rows: return False\n    item=rows[0]\n    pending=db("lista_proxima",params={"select":"*"})\n    same=next((p for p in pending if norm(p.get("nome_produto"))==norm(item.get("nome_produto"))),None)\n    if same:\n        new_qty=num(same.get("quantidade"))+num(item.get("quantidade"))\n        db("lista_proxima","PATCH",params={"id":f"eq.{same['id']}"},data={"quantidade":new_qty,"preco_estimado":num(same.get("preco_estimado")) or num(item.get("preco_estimado")),"atualizado_em":now()})\n    else:\n        db("lista_proxima","POST",data={"nome_produto":item.get("nome_produto"),"categoria":item.get("categoria","Mercearia"),"unidade":item.get("unidade","un."),"quantidade":num(item.get("quantidade")),"preco_estimado":num(item.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now()})\n    db("lista_atual","DELETE",params={"id":f"eq.{item_id}"})\n    clear()\n    return True\n\ndef restore_next_list():\n    pending=db("lista_proxima",params={"select":"*","order":"id.asc"})\n    if not pending: return 0\n    rows=[{"nome_produto":x.get("nome_produto"),"categoria":x.get("categoria","Mercearia"),"unidade":x.get("unidade","un."),"quantidade":num(x.get("quantidade")),"preco_estimado":num(x.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now()} for x in pending]\n    db("lista_atual","POST",data=rows)\n    db("lista_proxima","DELETE",params={"id":"gt.0"})\n    clear()\n    return len(rows)\n\n'''
if 'def move_item_to_next_list' not in _source:
    _source = _source.replace('def add_item(', _next_helpers + 'def add_item(', 1)

# Orçamento: permitir iniciar a próxima lista.
_source = _source.replace('st.session_state["open_add_after_budget" if action=="add" else "open_standard_after_budget"]=True','st.session_state["open_add_after_budget" if action=="add" else ("open_next_after_budget" if action=="next" else "open_standard_after_budget")]=True',1)
_source = _source.replace('    if st.session_state.pop("open_add_after_budget",False): add_list_dialog(products)','    if st.session_state.pop("open_next_after_budget",False):\n        restore_next_list()\n        st.rerun()\n    if st.session_state.pop("open_add_after_budget",False): add_list_dialog(products)',1)

# Quando não houver lista atual, mostrar a próxima lista pendente.
_old_empty = '''    if not current: st.markdown('<div class="empty"><strong>Sua lista está vazia.</strong><br>Ao iniciar uma nova compra, o sistema solicitará o orçamento antes do primeiro item.</div>',unsafe_allow_html=True)'''
_new_empty = '''    if not current:\n        _pending_next=db("lista_proxima",params={"select":"id,nome_produto,quantidade","order":"id.asc"})\n        if _pending_next:\n            st.info(f"Há {len(_pending_next)} item(ns) guardado(s) para a próxima lista.")\n            if st.button("Iniciar próxima compra",type="primary",use_container_width=True,key="start_next_purchase"):\n                budget_dialog("next")\n        else:\n            st.markdown('<div class="empty"><strong>Sua lista está vazia.</strong><br>Ao iniciar uma nova compra, o sistema solicitará o orçamento antes do primeiro item.</div>',unsafe_allow_html=True)'''
if _old_empty in _source:
    _source = _source.replace(_old_empty, _new_empty, 1)

# Adiciona o comando Próxima lista aos cards.
_source = _source.replace('d1,d2,d3=st.columns(3)', 'd1,d2,d3,d4=st.columns(4)', 1)
_old_d3 = '''        with d3:\n            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()\n'''
_new_d3 = '''        with d3:\n            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()\n        with d4:\n            if not ok:\n                if st.button("Próxima lista",key=f"next_{item['id']}",use_container_width=True,help="Guarda este item para a próxima compra."):\n                    try:\n                        if move_item_to_next_list(item["id"]):\n                            st.toast("Item guardado para a próxima lista.")\n                            st.rerun()\n                    except Exception as e:\n                        st.error(f"Não foi possível guardar o item na próxima lista: {e}")\n            else:\n                st.button("Próxima lista",disabled=True,key=f"next_done_{item['id']}",use_container_width=True)\n'''
if _old_d3 in _source:
    _source = _source.replace(_old_d3, _new_d3, 1)

# Cadastro de produto: validação contra o banco em tempo real, evitando cache antigo.
_new_product_dialog = '''@st.dialog("Adicionar novo produto")\ndef new_product_dialog(products):\n    live_products=db("produtos",params={"select":"*","order":"nome.asc"})\n    cats=sorted(set(["Mercearia","Hortifruti","Carnes","Bebidas","Laticínios e ovos","Padaria","Congelados","Limpeza","Higiene pessoal","Casa e utilidades","Pet","Infantil","Saúde e farmácia"]+[p.get("categoria","Mercearia") for p in live_products]))\n    with st.form("new_product_form"):\n        name=st.text_input("Nome")\n        cat=st.selectbox("Categoria",cats)\n        unit=st.text_input("Unidade",value="un.")\n        if st.form_submit_button("Cadastrar produto",type="primary",use_container_width=True):\n            if not name.strip():\n                st.error("Informe o nome.")\n            elif not unit.strip():\n                st.error("Informe a unidade.")\n            elif find_product(live_products,name):\n                st.error(f"O produto '{name.strip()}' já está cadastrado. Não é possível cadastrar duplicado.")\n            else:\n                create_product(name,cat,unit,0,1)\n                clear()\n                st.rerun()\n'''
_source = re.sub(r'@st\.dialog\("Adicionar novo produto"\)\ndef new_product_dialog\(products\):.*?\ndef import_products_excel', _new_product_dialog + '\ndef import_products_excel', _source, count=1, flags=re.S)

# Execução.
exec(compile(_source, str(Path(__file__)), "exec"))
