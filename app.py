from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# Correção pontual: os helpers da próxima lista precisam existir no globals()
# que o 687107 usa para executar o app_original.
_helpers = '''

def move_item_to_next_list(item_id):
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

# O 687107 executa o 0074 no mesmo globals(); inserir aqui evita que o
# app_original encontre restore_next_list indefinida.
_marker = 'from pathlib import Path\nimport re\nimport urllib.request\n'
if _marker not in _source:
    raise RuntimeError("Ponto de injeção dos helpers não encontrado.")
_source = _source.replace(_marker, _marker + _helpers, 1)

# Mantém o fallback já necessário para o bloco de histórico.
_old_exec = 'exec(compile(_source, str(Path(__file__)), "exec"))'
_new_exec = 'import streamlit as st\nif "hist" not in globals():\n    hist = st.container()\n' + _old_exec
if _old_exec not in _source:
    raise RuntimeError("Ponto de execução do 687107 não encontrado.")
_source = _source.replace(_old_exec, _new_exec, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
