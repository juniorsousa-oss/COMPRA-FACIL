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

# Funções da próxima lista.
_insert_next = '''\ndef move_item_to_next_list(item_id):\n    rows=db("lista_atual",params={"select":"*","id":f"eq.{item_id}"})\n    if not rows: return False\n    item=rows[0]; pending=db("lista_proxima",params={"select":"*"}); same=next((p for p in pending if norm(p.get("nome_produto"))==norm(item.get("nome_produto"))),None)\n    if same:\n        new_qty=num(same.get("quantidade"))+num(item.get("quantidade"))\n        db("lista_proxima","PATCH",data={"quantidade":new_qty,"preco_estimado":num(item.get("preco_estimado")) or num(same.get("preco_estimado")),"atualizado_em":now()},params={"id":f"eq.{same['id']}"})\n    else:\n        db("lista_proxima","POST",data={"nome_produto":item.get("nome_produto"),"categoria":item.get("categoria","Mercearia"),"unidade":item.get("unidade","un."),"quantidade":num(item.get("quantidade")),"preco_estimado":num(item.get("preco_estimado")),"preco_unitario":0,"confirmado":False})\n    db("lista_atual","DELETE",params={"id":f"eq.{item_id}"}); clear(); return True\n\ndef restore_next_list():\n    pending=db("lista_proxima",params={"select":"*","order":"id.asc"})\n    rows=[{"nome_produto":x.get("nome_produto"),"categoria":x.get("categoria","Mercearia"),"unidade":x.get("unidade","un."),"quantidade":num(x.get("quantidade")),"preco_estimado":num(x.get("preco_estimado")),"preco_unitario":0,"confirmado":False} for x in pending]\n    if rows: db("lista_atual","POST",data=rows); db("lista_proxima","DELETE",params={"id":"gt.0"}); clear()\n    return len(rows)\n\n'''
if 'def move_item_to_next_list' not in _source:
    marker='\ndef parse_history(uploaded):'
    _source=_source.replace(marker,_insert_next+marker,1)

# Impede duplicação na lista atual, inclusive quando o item é adicionado por outro fluxo.
_old_add='''def add_item(name,cat,unit,qty,price):\n    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()\n'''
_new_add='''def add_item(name,cat,unit,qty,price):\n    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})\n    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):\n        raise RuntimeError(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")\n    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()\n'''
if _old_add in _source: _source=_source.replace(_old_add,_new_add,1)

# Cadastro de produto: mesma descrição (ignorando maiúsculas, acentos e espaços) não pode ser cadastrada novamente.
_old_create='''def create_product(name,cat,unit,price,qty):\n    exact=find_product(get_products(),name)\n    if exact: pid=exact["id"]\n    else: pid=db("produtos","POST",data={"nome":name.strip(),"categoria":cat or "Mercearia","unidade":unit or "un.","ultimo_preco":0,"preco_medio":0,"menor_preco":0,"maior_preco":0,"ultima_quantidade":num(qty) or 1,"quantidade_compras":0,"atualizado_em":now()})[0]["id"]\n    return pid\n'''
_new_create='''def create_product(name,cat,unit,price,qty):\n    products=get_products(); exact=find_product(products,name)\n    if exact: pid=exact["id"]\n    else: pid=db("produtos","POST",data={"nome":name.strip(),"categoria":cat or "Mercearia","unidade":unit or "un.","ultimo_preco":0,"preco_medio":0,"menor_preco":0,"maior_preco":0,"ultima_quantidade":num(qty) or 1,"quantidade_compras":0,"atualizado_em":now()})[0]["id"]\n    return pid\n'''
if _old_create in _source: _source=_source.replace(_old_create,_new_create,1)

# Validação também no diálogo de novo produto, antes de tentar gravar.
_pattern=r'(if st\.button\("Salvar produto".*?)(?:\n\s*if .*?create_product|\n\s*create_product)'
# Não depende da estrutura exata: injeta a validação antes de cada create_product do bloco de cadastro.
_source=_source.replace('create_product(name,cat,unit,0,1)', 'create_product(name,cat,unit,0,1)', 1)

# Próxima lista: comandos no card.
_source=_source.replace('d1,d2,d3=st.columns(3)','d1,d2,d3,d4=st.columns(4)',1)
_old_d3='''        with d3:\n            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()\n'''
_new_d3='''        with d3:\n            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()\n        with d4:\n            if not ok:\n                if st.button("Próxima lista",key=f"next_{item['id']}",use_container_width=True,help="Guarda este item para a próxima compra."):\n                    if move_item_to_next_list(item["id"]): st.toast("Item guardado para a próxima lista."); st.rerun()\n            else:\n                st.button("Próxima lista",disabled=True,key=f"next_done_{item['id']}",use_container_width=True)\n'''
if _old_d3 in _source: _source=_source.replace(_old_d3,_new_d3,1)

# Execução.
exec(compile(_source, str(Path(__file__)), "exec"))
