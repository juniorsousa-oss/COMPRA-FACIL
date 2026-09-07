from pathlib import Path
import urllib.request

# Mantém como base a versão que já continha a Próxima lista.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# As correções abaixo são aplicadas no código real (app_original.py),
# e não apenas no wrapper intermediário.
_deep_patch = r"""
# --- correções pontuais aplicadas no app_original.py ---

# 1) Bloqueio de duplicidade sem derrubar o Streamlit.
_source = re.sub(r"def add_item\(name,cat,unit,qty,price\):.*?(?=\ndef edit_item)", '''def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto **{name.strip()}** já está nesta lista. Altere a quantidade no item já adicionado.")
        return False
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()})
    clear()
    return True
''', _source, count=1, flags=re.S)

# 2) Garante as funções da Próxima lista no mesmo escopo do add_item real.
if "def move_item_to_next_list(item_id):" not in _source:
    _next_helpers_runtime = '''def move_item_to_next_list(item_id):
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
    _source = _source.replace("def add_item(", _next_helpers_runtime + "def add_item(", 1)

# 3) Garante Desconfirmar para item já confirmado.
_old_confirm_runtime = '''        with d1:
            st.button("Confirmado",disabled=True,use_container_width=True,key=f"c_done_{item['id']}") if ok else None
            if not ok and st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True): st.session_state["confirm_item"]=item; st.rerun()
'''
_new_confirm_runtime = '''        with d1:
            if ok:
                if st.button("Desconfirmar",use_container_width=True,key=f"unconfirm_{item['id']}"):
                    edit_item(item["id"],confirmado=False)
                    st.rerun()
            else:
                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True):
                    st.session_state["confirm_item"]=item
                    st.rerun()
'''
if _old_confirm_runtime in _source:
    _source = _source.replace(_old_confirm_runtime, _new_confirm_runtime, 1)

# 4) Se ainda estiver com 3 colunas, mantém a ação Próxima lista.
_source = _source.replace('        d1,d2,d3=st.columns(3)', '        d1,d2,d3,d4=st.columns(4)', 1)
_old_delete_runtime = '''        with d3:
            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()
'''
_new_delete_runtime = '''        with d3:
            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True): remove_item(item["id"]); st.rerun()
        with d4:
            if not ok:
                if st.button("Próxima lista",key=f"next_{item['id']}",use_container_width=True,help="Guarda este item para a próxima compra."):
                    try:
                        if move_item_to_next_list(item["id"]):
                            st.toast("Item guardado para a próxima lista.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível guardar o item na próxima lista: {e}")
            else:
                st.button("Próxima lista",disabled=True,key=f"next_done_{item['id']}",use_container_width=True)
'''
if _old_delete_runtime in _source:
    _source = _source.replace(_old_delete_runtime, _new_delete_runtime, 1)

# 5) Não faz rerun quando a duplicidade for recusada.
_old_add_ui_runtime = '                    add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))); st.rerun()'
_new_add_ui_runtime = '''                    if add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))):
                        st.rerun()'''
_source = _source.replace(_old_add_ui_runtime, _new_add_ui_runtime, 1)
"""

# 687107 executa o wrapper 0074. Inserimos o patch no final desse wrapper,
# depois que ele já aplicou os patches anteriores sobre app_original.py.
_exec = 'exec(compile(_source, str(Path(__file__)), "exec"))'
if _exec in _source:
    _inject = f'_source = _source.replace({_exec!r}, {_deep_patch!r} + "\\n" + {_exec!r}, 1)\n' + _exec
    _source = _source.replace(_exec, _inject, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
