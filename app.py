from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687 ja contem as correcoes funcionais da proxima lista e demais ajustes.
# Corrigimos a duplicidade no nivel correto: o 0074 carrega o app_original
# como texto e somente depois o executa.
_patch_0074 = r'''
_dup_exec = 'exec(compile(_source,"app_original.py","exec"),globals(),globals())'
_old_add = '''def add_item(name,cat,unit,qty,price):
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()'''
_new_add = '''def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
        return
    try:
        db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()})
    except RuntimeError as e:
        if "23505" in str(e) and "ux_lista_atual_nome_normalizado" in str(e):
            st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
            return
        raise
    clear()'''
if _old_add not in _source:
    raise RuntimeError("Função add_item original não encontrada para correção de duplicidade.")
_source = _source.replace(_old_add,_new_add,1)
'''

# Insere o patch acima dentro do 0074 antes que ele execute o app_original.
_0074_exec = 'exec(compile(_source,"app_original.py","exec"),globals(),globals())'
if _0074_exec not in _source:
    raise RuntimeError("Ponto de execução do 0074 não encontrado.")
_source = _source.replace(_0074_exec, _patch_0074 + '\n' + _0074_exec, 1)

# Fallback para o container do histórico em reruns de dialog/fragment.
_old_exec = 'exec(compile(_source, str(Path(__file__)), "exec"))'
_new_exec = 'import streamlit as st\nif "hist" not in globals():\n    hist = st.container()\n' + _old_exec
if _old_exec not in _source:
    raise RuntimeError("Ponto de execução do wrapper não encontrado.")
_source = _source.replace(_old_exec, _new_exec, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
