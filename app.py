from pathlib import Path
import urllib.request

# Base estável: mantém Próxima lista + Desconfirmar já validados.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# Corrige somente a camada que executa app_original.py.
# O patch anterior tentava alterar o código dentro de outra camada de wrapper
# e não chegava à função add_item efetivamente executada pelo Streamlit.
_inject_after = '_source = _original.read_text(encoding="utf-8")'
_injected = '''_source = _original.read_text(encoding="utf-8")
_old_add_runtime = ''' + repr('''def add_item(name,cat,unit,qty,price):
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()
''') + '''
_new_add_runtime = ''' + repr('''def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto","id":"gt.0"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto **{name.strip()}** já está nesta lista. Altere a quantidade no item já adicionado.")
        return False
    db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()}); clear()
    return True
''') + '''
_source = _source.replace(_old_add_runtime, _new_add_runtime, 1)
_old_add_ui_runtime = '                    add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))); st.rerun()'
_new_add_ui_runtime = '                    if add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))):\\n                        st.rerun()'
_source = _source.replace(_old_add_ui_runtime, _new_add_ui_runtime, 1)'''
_patch = '''_source = _source.replace(_inject_after, _injected, 1)'''
_source = _source.replace('_source = _source.replace(\'_source = _original.read_text(encoding="utf-8")\'', _patch, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
