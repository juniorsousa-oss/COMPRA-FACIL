from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687 já contém as correções funcionais da próxima lista e demais ajustes.
# Apenas trocamos o erro proposital de duplicidade por um aviso amigável.
_old = '''raise RuntimeError(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")'''
_new = '''st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
        st.stop()'''
if _old not in _source:
    raise RuntimeError("Ponto de duplicidade não encontrado no wrapper.")
_source = _source.replace(_old, _new, 1)

# Fallback para o container do histórico em reruns de dialog/fragment.
_old_exec = 'exec(compile(_source, str(Path(__file__)), "exec"))'
_new_exec = 'import streamlit as st\nif "hist" not in globals():\n    hist = st.container()\n' + _old_exec
if _old_exec not in _source:
    raise RuntimeError("Ponto de execução do wrapper não encontrado.")
_source = _source.replace(_old_exec, _new_exec, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
