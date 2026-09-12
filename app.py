from pathlib import Path
import urllib.request
import streamlit as st

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

safe_add = '''def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
        st.stop()
    try:
        db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()})
    except RuntimeError as e:
        if "23505" in str(e):
            st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
            st.stop()
        raise
    clear()
'''

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

# Este bloco precisa ser executado dentro do wrapper 0074, porque é nele
# que _source já contém o texto final de app_original.py.
inner = (
    "\nimport re as _patch_re\n"
    "if 'def move_item_to_next_list' not in _source:\n"
    "    _source = _source.replace('def add_item(', " + repr(next_helpers + "def add_item(") + ", 1)\n"
    "_patch_pattern = r'def add_item\\(name,cat,unit,qty,price\\):.*?\\ndef edit_item'\n"
    "_source, _patch_count = _patch_re.subn(_patch_pattern, " + repr(safe_add + "\ndef edit_item") + ", _source, count=1, flags=_patch_re.S)\n"
    "if _patch_count != 1:\n"
    "    raise RuntimeError('Tratamento de item duplicado nao foi aplicado.')\n"
)

# A fonte carregada aqui é o wrapper 687. Antes de ele executar o 0074,
# inserimos no texto do 0074 o patch acima. O marcador abaixo é o final
# real do 0074, não o final do 687.
inner_marker = 'exec(compile(_source,"app_original.py","exec"),globals(),globals())'
outer_marker = 'exec(compile(_source, str(Path(__file__)), "exec"))'
bridge = (
    "\n_inner_marker = " + repr(inner_marker) + "\n"
    "_inner_patch = " + repr(inner) + "\n"
    "if _inner_marker not in _source:\n"
    "    raise RuntimeError('Ponto de execucao do app_original nao encontrado no 0074.')\n"
    "_source = _source.replace(_inner_marker, _inner_patch + _inner_marker, 1)\n"
)

pos = source.rfind(outer_marker)
if pos < 0:
    raise RuntimeError("Execucao do 687 nao encontrada.")
source = source[:pos] + bridge + source[pos:]

if "hist" not in globals():
    hist = st.container()

exec(compile(source, str(Path(__file__)), "exec"))