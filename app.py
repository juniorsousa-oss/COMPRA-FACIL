from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

old = """def add_item(name,cat,unit,qty,price):
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()
"""
new = """def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto '{name.strip()}' ja esta nesta lista. Altere a quantidade no item ja adicionado.")
        return
    try:
        db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()})
    except RuntimeError as e:
        if "23505" in str(e):
            st.warning(f"O produto '{name.strip()}' ja esta nesta lista. Altere a quantidade no item ja adicionado.")
            return
        raise
    clear()
"""

# 0074 le o arquivo original em _source. Insira a substituicao logo depois dessa leitura.
patch = "\nimport streamlit as st\n_source = _source.replace(" + repr(old) + ", " + repr(new) + ", 1)\n"
needle = '_source = _original.read_text(encoding="utf-8")'
pos = _source.find(needle)
if pos < 0:
    raise RuntimeError("Leitura do arquivo base nao encontrada.")
insert = pos + len(needle)
_source = _source[:insert] + patch + _source[insert:]

if "hist" not in globals():
    hist = st.container()

exec(compile(_source, str(Path(__file__)), "exec"))