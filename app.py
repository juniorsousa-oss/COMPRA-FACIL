from pathlib import Path
import urllib.request
import streamlit as st

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687107 carrega o 0074 e executa o app_original no mesmo globals().
# O erro ocorre porque um rerun de dialog/fragment pode chegar ao bloco
# 'with hist:' sem que a variável da aba tenha sido criada naquele escopo.
# Mantemos a aba original quando ela existe e apenas fornecemos um container
# seguro como fallback, sem alterar a lógica das demais abas.
_old_exec = 'exec(compile(_source, str(Path(__file__)), "exec"))'
_new_exec = 'import streamlit as st\nif "hist" not in globals():\n    hist = st.container()\n' + _old_exec
if _old_exec not in _source:
    raise RuntimeError("Ponto de execução do 687107 não encontrado.")
_source = _source.replace(_old_exec, _new_exec, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
