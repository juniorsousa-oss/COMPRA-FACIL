from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687 carrega o 0074, que por sua vez executa o app_original.
# Não alteramos o app_original por string aninhada: executamos o 0074 normalmente
# e, ao final, sobrescrevemos apenas add_item para tratar duplicidade.
_0074_exec = 'exec(compile(_source, str(Path(__file__)), "exec"))'
if _0074_exec not in _source:
    raise RuntimeError("Ponto de execução do 0074 não encontrado.")

_source = _source.replace(_0074_exec, _0074_exec + '''

# Correção pontual da duplicidade na lista atual.
def add_item(name,cat,unit,qty,price):
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
    clear()
''', 1)

# Mantém o fallback já necessário para o histórico.
if "hist" not in globals():
    hist = st.container()

exec(compile(_source, str(Path(__file__)), "exec"))
