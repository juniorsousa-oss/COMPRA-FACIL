from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687107 carrega o 0074 e executa o app_original no mesmo globals().
# Mantemos as correções já existentes e apenas garantimos que os helpers
# da próxima lista estejam disponíveis no mesmo escopo do app_original.
_helpers = '''\ndef move_item_to_next_list(item_id):
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

# Define os helpers no globals() antes de executar o código antigo.
# As dependências (db, num, norm, now, clear) são resolvidas somente quando
# as funções forem chamadas, depois que app_original já as tiver definido.
_source = _source.replace(
    'exec(compile(_source, str(Path(__file__)), "exec"))',
    '_source = _source.replace("from pathlib import Path\\nimport re\\nimport urllib.request", "from pathlib import Path\\nimport re\\nimport urllib.request" + _helpers, 1)\nexec(compile(_source, str(Path(__file__)), "exec"))',
    1,
)

# Fallback para o container do histórico em reruns de dialog/fragment.
_source = _source.replace(
    'exec(compile(_source, str(Path(__file__)), "exec"))',
    'import streamlit as st\\nif "hist" not in globals():\\n    hist = st.container()\\n' + 'exec(compile(_source, str(Path(__file__)), "exec"))',
    1,
)

exec(compile(_source, str(Path(__file__)), "exec"))
