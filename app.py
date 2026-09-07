from pathlib import Path
import urllib.request

# Base estável: mantém Próxima lista + Desconfirmar já validados.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# Correção isolada: impedir duplicidade na lista atual.
_needle = '_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")'
_injected = '''_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")

# Correção isolada: impedir duplicidade na lista atual.
_runtime_old_add = ''' + repr('''def add_item(name,cat,unit,qty,price):
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()
''') + '''
_runtime_new_add = ''' + repr('''def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto **{name.strip()}** já está nesta lista. Altere a quantidade no item já adicionado.")
        st.stop()
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()
''') + '''
_source = _source.replace(_runtime_old_add, _runtime_new_add, 1)

# Rerun do diálogo da próxima lista pode ocorrer antes da criação das tabs.
# Cria apenas um container temporário nesse caso, sem alterar a aba normal.
_source = _source.replace('with hist:', 'if "hist" not in globals(): hist=st.container()\nwith hist:', 1)
'''
_source = _source.replace(_needle, _injected, 1)

exec(compile(_source, str(Path(__file__)), "exec"))