from pathlib import Path
import re
import urllib.request

# Base estável: mantém Próxima lista + Desconfirmar já validados.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# Corrige somente o bloco de inclusão duplicada dentro do patch que monta
# app_original.py. A versão anterior ainda deixava o raise RuntimeError.
_old_block = '''_new_add = '''
def _noop(): pass
'''
# Substituição direcionada pela estrutura do _new_add do 687107.
_source = re.sub(
    r'''_new_add = ''' + "'''" + r'''def add_item\(name,cat,unit,qty,price\):\\n    existing=.*?if any\(norm\(x\.get\("nome_produto"\)\)==norm\(name\) for x in existing\):\\n        raise RuntimeError\(.*?\)\\n    db\("lista_atual","POST",data=\{.*?\}\); clear\(\)\\n''' + "'''",
    "_new_add = '''def add_item(name,cat,unit,qty,price):\\n    existing=db(\\\"lista_atual\\\",params={\\\"select\\\":\\\"id,nome_produto\\\",\\\"id\\\":\\\"gt.0\\\"})\\n    if any(norm(x.get(\\\"nome_produto\\\"))==norm(name) for x in existing):\\n        st.warning(f\\\"O produto **{name.strip()}** já está nesta lista. Altere a quantidade no item já adicionado.\\\")\\n        return False\\n    db(\\\"lista_atual\\\",\\\"POST\\\",data={\\\"nome_produto\\\":name.strip(),\\\"categoria\\\":cat,\\\"unidade\\\":unit or \\\"un.\\\",\\\"quantidade\\\":num(qty),\\\"preco_estimado\\\":num(price),\\\"preco_unitario\\\":0,\\\"confirmado\\\":False,\\\"atualizado_em\\\":now()}); clear()\\n    return True\\n'''",
    _source,
    count=1,
    flags=re.S,
)

# Evita rerun quando add_item retornar False.
_source = _source.replace(
    'add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))); st.rerun()',
    'if add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))):\\n                        st.rerun()',
    1,
)

exec(compile(_source, str(Path(__file__)), "exec"))
