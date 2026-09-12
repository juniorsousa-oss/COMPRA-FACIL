from pathlib import Path
import urllib.request
import streamlit as st

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

old = "def add_item(name,cat,unit,qty,price):\n    db(\"lista_atual\",\"POST\",data={\"nome_produto\":name.strip(),\"categoria\":cat,\"unidade\":unit or \"un.\",\"quantidade\":num(qty),\"preco_estimado\":num(price),\"preco_unitario\":0,\"confirmado\":False,\"atualizado_em\":now()}); clear()\n"
new = "def add_item(name,cat,unit,qty,price):\n    existing=db(\"lista_atual\",params={\"select\":\"id,nome_produto\",\"id\":\"gt.0\"})\n    if any(norm(x.get(\"nome_produto\"))==norm(name) for x in existing):\n        st.warning(f\"O produto '{name.strip()}' ja esta nesta lista. Altere a quantidade no item ja adicionado.\")\n        return\n    try:\n        db(\"lista_atual\",\"POST\",data={\"nome_produto\":name.strip(),\"categoria\":cat,\"unidade\":unit or \"un.\",\"quantidade\":num(qty),\"preco_estimado\":num(price),\"preco_unitario\":0,\"confirmado\":False,\"atualizado_em\":now()})\n    except RuntimeError as e:\n        if \"23505\" in str(e):\n            st.warning(f\"O produto '{name.strip()}' ja esta nesta lista. Altere a quantidade no item ja adicionado.\")\n            return\n        raise\n    clear()\n"

next_helpers = '''def move_item_to_next_list(item_id):
    rows=db("lista_atual",params={"select":"*","id":f"eq.{item_id}"})
    if not rows:
        return False
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
    if not pending:
        return 0
    rows=[{"nome_produto":x.get("nome_produto"),"categoria":x.get("categoria","Mercearia"),"unidade":x.get("unidade","un."),"quantidade":num(x.get("quantidade")),"preco_estimado":num(x.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now()} for x in pending]
    db("lista_atual","POST",data=rows)
    db("lista_proxima","DELETE",params={"id":"gt.0"})
    clear()
    return len(rows)

'''

# O 687 contem o codigo do 0074. Inserimos dentro dele uma pequena
# correcao que o 0074 executara depois de carregar e montar app_original.
# Aqui entram somente as funcoes que faltavam para a funcionalidade
# "Proxima lista" e a protecao ja existente contra item duplicado.
inner = (
    "\n"
    "if 'def move_item_to_next_list' not in _source:\n"
    "    _source = _source.replace('def add_item(', " + repr(next_helpers + "def add_item(") + ", 1)\n"
    "_source = _source.replace(" + repr(old) + ", " + repr(new) + ", 1)\n"
)

marker = 'exec(compile(_source, str(Path(__file__)), "exec"))'
inject = "\n_patch_marker = " + repr(marker) + "\n_patch_inner = " + repr(inner) + "\n_source = _source.replace(_patch_marker, _patch_inner + _patch_marker, 1)\n"

pos = source.rfind(marker)
if pos < 0:
    raise RuntimeError("Execucao do 687 nao encontrada.")
source = source[:pos] + inject + source[pos:]

if "hist" not in globals():
    hist = st.container()

exec(compile(source, str(Path(__file__)), "exec"))