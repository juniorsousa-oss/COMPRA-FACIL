from pathlib import Path
import urllib.request

# Base estável: mantém Próxima lista + Desconfirmar já validados.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687107 carrega o wrapper 0074. Inserimos o ajuste diretamente no
# código do 0074, para que ele altere a função add_item real do app_original.
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
        return False
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()
    return True
''') + '''
_runtime_source_patch = ''' + repr('''_source = _source.replace(_runtime_old_add, _runtime_new_add, 1)
_old_add_ui_runtime = '                    add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))); st.rerun()'
_new_add_ui_runtime = '                    if add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))):\\n                        st.rerun()'
_source = _source.replace(_old_add_ui_runtime, _new_add_ui_runtime, 1)''') + '''
exec(_runtime_source_patch)
'''
_source = _source.replace(_needle, _injected, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
