from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

_old_add = """def add_item(name,cat,unit,qty,price):
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()
"""
_new_add = """def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto '{name.strip()}' ja esta nesta lista. Altere a quantidade no item ja adicionado.")
        return
    try:
        db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()})
    except RuntimeError as e:
        if "23505" in str(e) and "ux_lista_atual_nome_normalizado" in str(e):
            st.warning(f"O produto '{name.strip()}' ja esta nesta lista. Altere a quantidade no item ja adicionado.")
            return
        raise
    clear()
"""

# Gera o codigo que sera inserido dentro do 0074.
_patch_0074 = (
    "\nimport streamlit as st\n"
    "_old_add_runtime = " + repr(_old_add) + "\n"
    "_new_add_runtime = " + repr(_new_add) + "\n"
    "if _old_add_runtime in _source:\n"
    "    _source = _source.replace(_old_add_runtime, _new_add_runtime, 1)\n"
)

# Insere o patch imediatamente antes da execucao final do 0074.
_marker = 'exec(compile(_source, str(Path(__file__)), "exec"))'
_pos = _source.rfind(_marker)
if _pos < 0:
    _pos = _source.rfind("exec(compile(_source")
    if _pos < 0:
        raise RuntimeError("Nao foi possivel localizar a execucao do 0074.")

_source = _source[:_pos] + _patch_0074 + _source[_pos:]

# Fallback para o container do historico.
if "hist" not in globals():
    hist = st.container()

exec(compile(_source, str(Path(__file__)), "exec"))