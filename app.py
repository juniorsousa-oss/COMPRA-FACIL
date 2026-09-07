from pathlib import Path
import urllib.request
import streamlit as st

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

old = "def add_item(name,cat,unit,qty,price):\n    db(\"lista_atual\",\"POST\",data={\"nome_produto\":name.strip(),\"categoria\":cat,\"unidade\":unit or \"un.\",\"quantidade\":num(qty),\"preco_estimado\":num(price),\"preco_unitario\":0,\"confirmado\":False,\"atualizado_em\":now()}); clear()\n"
new = "def add_item(name,cat,unit,qty,price):\n    existing=db(\"lista_atual\",params={\"select\":\"id,nome_produto\",\"id\":\"gt.0\"})\n    if any(norm(x.get(\"nome_produto\"))==norm(name) for x in existing):\n        st.warning(f\"O produto '{name.strip()}' ja esta nesta lista. Altere a quantidade no item ja adicionado.\")\n        return\n    try:\n        db(\"lista_atual\",\"POST\",data={\"nome_produto\":name.strip(),\"categoria\":cat,\"unidade\":unit or \"un.\",\"quantidade\":num(qty),\"preco_estimado\":num(price),\"preco_unitario\":0,\"confirmado\":False,\"atualizado_em\":now()})\n    except RuntimeError as e:\n        if \"23505\" in str(e):\n            st.warning(f\"O produto '{name.strip()}' ja esta nesta lista. Altere a quantidade no item ja adicionado.\")\n            return\n        raise\n    clear()\n"

# O 687 contem o codigo do 0074. Antes do exec final do 0074,
# substituimos add_item no texto do app_original que o 0074 executara.
patch = "\n_patch_old = " + repr(old) + "\n_patch_new = " + repr(new) + "\n_source = _source.replace(_patch_old, _patch_new, 1)\n"
marker = 'exec(compile(_source, str(Path(__file__)), "exec"))'
pos = source.rfind(marker)
if pos < 0:
    raise RuntimeError("Execucao do 687 nao encontrada.")
source = source[:pos] + patch + source[pos:]

if "hist" not in globals():
    hist = st.container()

exec(compile(source, str(Path(__file__)), "exec"))