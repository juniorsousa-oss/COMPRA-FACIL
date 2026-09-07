from pathlib import Path
import re
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# Corrige a duplicidade no nivel correto: o 0074 carrega o app_original
# como texto e somente depois o executa.
_patch_0074 = r'''
_old_add = """def add_item(name,cat,unit,qty,price):
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()"""
_new_add = """def add_item(name,cat,unit,qty,price):
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
    clear()"""
if _old_add not in _source:
    raise RuntimeError("Função add_item original não encontrada para correção de duplicidade.")
_source = _source.replace(_old_add, _new_add, 1)
'''

# Em vez de procurar a linha inteira de exec, usa uma expressão que aceita
# espaços diferentes no compile. Isso evita o erro anterior do marcador.
_marker = re.compile(r'compile\(_source\s*,\s*["\']app_original\.py["\']\s*,\s*["\']exec["\']\)')
if not _marker.search(_source):
    raise RuntimeError("Ponto de execução do app_original não encontrado.")
_source = _marker.sub(_patch_0074 + '\ncompile(_source,"app_original.py","exec")', _source, count=1)

# Fallback para o container do histórico em reruns de dialog/fragment.
_old_exec = 'exec(compile(_source, str(Path(__file__)), "exec"))'
_new_exec = 'import streamlit as st\nif "hist" not in globals():\n    hist = st.container()\n' + _old_exec
if _old_exec not in _source:
    raise RuntimeError("Ponto de execução do wrapper não encontrado.")
_source = _source.replace(_old_exec, _new_exec, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
