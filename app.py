from pathlib import Path
import re
import urllib.request

# Usa a versão estável que já contém os ajustes anteriores.
_BASE_URL = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/0074e6f1fe2b4bfdee87793c6bff1fec391d35cc/app.py"
_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")

# Em itens confirmados, substitui o botão desabilitado por Desconfirmar.
_old = '''        with d1:\n            st.button("Confirmado",disabled=True,use_container_width=True,key=f"c_done_{item['id']}") if ok else None\n            if not ok and st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True): st.session_state["confirm_item"]=item; st.rerun()\n'''
_new = '''        with d1:\n            if ok:\n                if st.button("Desconfirmar",use_container_width=True,key=f"unconfirm_{item['id']}"):\n                    edit_item(item["id"],confirmado=False)\n                    st.rerun()\n            else:\n                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True):\n                    st.session_state["confirm_item"]=item\n                    st.rerun()\n'''
if _old not in _source:
    raise RuntimeError("Bloco do botão de confirmação não encontrado.")
_source = _source.replace(_old, _new, 1)

# Guarda itens que não foram encontrados no supermercado para a próxima compra.
_insert_next = '''\ndef move_item_to_next_list(item_id):\n    rows=db("lista_atual",params={"select":"*","id":f"eq.{item_id}"})\n    if not rows:\n        return False\n    item=rows[0]\n    pending=db("lista_proxima",params={"select":"*"})\n    same=None\n    for p in pending:\n        if norm(p.get("nome_produto"))==norm(item.get("nome_produto")):\n            same=p\n            break\n    if same:\n        new_qty=num(same.get("quantidade"))+num(item.get("quantidade"))\n        db("lista_proxima","PATCH",data={"quantidade":new_qty,"preco_estimado":num(item.get("preco_estimado")) or num(same.get("preco_estimado")),"atualizado_em":now()},params={"id":f"eq.{same['id']}"})\n    else:\n        db("lista_proxima","POST",data={"nome_produto":item.get("nome_produto"),"categoria":item.get("categoria","Mercearia"),"unidade":item.get("unidade","un."),"quantidade":num(item.get("quantidade")),"preco_estimado":num(item.get("preco_estimado")),"preco_unitario":0,"confirmado":False})\n    db("lista_atual","DELETE",params={"id":f"eq.{item_id}"})\n    return True\n\ndef restore_next_list():\n    pending=db("lista_proxima",params={"select":"*","order":"id.asc"})\n    if not pending:\n        return 0\n    rows=[]\n    for item in pending:\n        rows.append({"nome_produto":item.get("nome_produto"),"categoria":item.get("categoria","Mercearia"),"unidade":item.get("unidade","un."),"quantidade":num(item.get("quantidade")),"preco_estimado":num(item.get("preco_estimado")),"preco_unitario":0,"confirmado":False})\n    db("lista_atual","POST",data=rows)\n    db("lista_proxima","DELETE",params={"id":"gt.0"})\n    return len(rows)\n\n'''
_source = _source.replace('\n# Executa o app já corrigido.\n', _insert_next + '\n# Executa o app já corrigido.\n', 1) if '\n# Executa o app já corrigido.\n' in _source else _source

# Permite iniciar a próxima lista usando o mesmo diálogo de orçamento.
_old_budget = '''        save_budget(value)\n        st.session_state["open_add_after_budget" if action=="add" else "open_standard_after_budget"]=True\n        st.rerun()\n'''
_new_budget = '''        save_budget(value)\n        if action=="add":\n            st.session_state["open_add_after_budget"]=True\n        elif action=="standard":\n            st.session_state["open_standard_after_budget"]=True\n        else:\n            st.session_state["open_next_after_budget"]=True\n        st.rerun()\n'''
if _old_budget not in _source:
    raise RuntimeError("Fluxo do orçamento não encontrado.")
_source = _source.replace(_old_budget, _new_budget, 1)

# Ação de mover fica no próprio card do item. Itens confirmados continuam sendo tratados como comprados.
_old_cols = '        d1,d2,d3=st.columns(3)\n'
_new_cols = '        d1,d2,d3,d4=st.columns(4)\n'
if _old_cols not in _source:
    raise RuntimeError("Colunas dos comandos do item não encontradas.")
_source = _source.replace(_old_cols, _new_cols, 1)

_old_d3 = '''        with d3:\n            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()\n'''
_new_d3 = '''        with d3:\n            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()\n        with d4:\n            if not ok:\n                if st.button("Próxima lista",key=f"next_{item['id']}",use_container_width=True,help="Retira este item da compra atual e guarda para a próxima compra."):\n                    if move_item_to_next_list(item["id"]):\n                        st.toast("Item guardado para a próxima lista.")\n                        st.rerun()\n            else:\n                st.button("Próxima lista",disabled=True,use_container_width=True,key=f"next_done_{item['id']}")\n'''
if _old_d3 not in _source:
    raise RuntimeError("Bloco Excluir do item não encontrado.")
_source = _source.replace(_old_d3, _new_d3, 1)

# Exibe a quantidade de itens já separados para a próxima compra e permite iniciar essa lista com novo orçamento.
_source = _source.replace('with buy:\n    st.subheader("Lista de compras")\n', '''with buy:\n    st.subheader("Lista de compras")\n    _pending_next=db("lista_proxima",params={"select":"id,nome_produto,quantidade"})\n    if st.session_state.pop("open_next_after_budget",False):\n        _restored=restore_next_list()\n        st.success(f"{_restored} item(ns) carregado(s) para a próxima compra.")\n        st.rerun()\n    if _pending_next and not current:\n        st.info(f"Há {len(_pending_next)} item(ns) guardado(s) para a próxima compra.")\n        if st.button("Iniciar próxima compra",type="primary",use_container_width=True,key="start_next_purchase"):\n            budget_dialog("next")\n''', 1)

# Executa o app já corrigido.
exec(compile(_source, str(Path(__file__)), "exec"))
