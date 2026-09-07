from pathlib import Path
import urllib.request

# Base estável que já contém as funcionalidades validadas.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687107 carrega o 0074, que por sua vez carrega app_original.py.
# Aplicamos a correção no nível em que app_original.py é realmente executado.
_nested_read = '_source = _original.read_text(encoding="utf-8")'
_nested_patch = '''_source = _original.read_text(encoding="utf-8")

# Em reruns de diálogos/fragments, as variáveis das tabs podem não existir.
# O container de fallback evita NameError sem alterar o fluxo normal das tabs.
_source = _source.replace('\\nwith hist:', '\\nif "hist" not in globals(): hist=st.container()\\nwith hist:', 1)

# Impede produto duplicado na lista atual.
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
'''

# Insere o patch acima dentro do código do 0074 antes que ele faça exec().
_injected_nested = _nested_patch
_source = _source.replace(_nested_read, _injected_nested, 1)

# Mantém o restante do 687107 intacto.
exec(compile(_source, str(Path(__file__)), "exec"))