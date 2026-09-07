from pathlib import Path
import urllib.request

# Base estável que já contém as funcionalidades validadas.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687107 carrega o 0074, que por sua vez carrega app_original.py.
# A correção precisa entrar no 0074 antes que ele leia/executa app_original.py.
_loader = '_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")'
_injected = '''_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")

# Injeta a correção no código do 0074, exatamente antes de ele carregar app_original.py.
_nested_read = '_source = _original.read_text(encoding="utf-8")'
_nested_patch = ''' + repr('''_source = _original.read_text(encoding="utf-8")

# Em reruns de st.dialog, as variáveis criadas por st.tabs podem não existir.
# Usa um container somente como fallback, sem alterar o fluxo normal das abas.
_source = _source.replace('\\nwith hist:', '\\nif "hist" not in globals(): hist=st.container()\\nwith hist:', 1)
''') + '''
_source = _source.replace(_nested_read, _nested_patch, 1)
'''
_source = _source.replace(_loader, _injected, 1)

# Mantém integralmente o restante do 687107 e suas funcionalidades já validadas.
exec(compile(_source, str(Path(__file__)), "exec"))