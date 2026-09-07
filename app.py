from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687 carrega o 0074. Antes que o 0074 execute o app_original,
# corrigimos somente a função add_item dentro do texto que será executado.
_0074_exec = 'exec(compile(_source, str(Path(__file__)), "exec"))'
if _0074_exec not in _source:
    raise RuntimeError("Ponto de execução do 0074 não encontrado.")

_patch_code = '''
import re as _re_patch
_source = _re_patch.sub(
    r'def add_item\\(name,cat,unit,qty,price\\):.*?clear\\(\\)\\n',
    'def add_item(name,cat,unit,qty,price):\\n'
    '    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})\\n'
    '    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):\\n'
    '        st.warning(f"O produto \'{name.strip()}\' já está nesta lista. Altere a quantidade no item já adicionado.")\\n'
    '        return\\n'
    '    try:\\n'
    '        db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()})\\n'
    '    except RuntimeError as e:\\n'
    '        if "23505" in str(e) and "ux_lista_atual_nome_normalizado" in str(e):\\n'
    '            st.warning(f"O produto \'{name.strip()}\' já está nesta lista. Altere a quantidade no item já adicionado.")\\n'
    '            return\\n'
    '        raise\\n'
    '    clear()\\n',
    _source,
    count=1,
    flags=_re_patch.S,
)
'''
_source = _source.replace(_0074_exec, _patch_code + '\n' + _0074_exec, 1)

# Fallback para o container do histórico.
if "hist" not in globals():
    hist = st.container()

exec(compile(_source, str(Path(__file__)), "exec"))
