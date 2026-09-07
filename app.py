from pathlib import Path
import urllib.request

# Base estável que já contém as funcionalidades validadas.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687107 carrega o 0074, que por sua vez carrega app_original.py.
# A correção precisa ser aplicada no texto do 0074 antes que ele execute app_original.py.
_loader = '_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")'
_injected = '''_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")

# st.dialog funciona como fragmento e pode executar sem as variáveis das tabs.
# Cria apenas um container de fallback para evitar NameError em hist.
_source = _source.replace("\\nwith hist:", "\\nif \\\"hist\\\" not in globals(): hist=st.container()\\nwith hist:", 1)
'''
_source = _source.replace(_loader, _injected, 1)

# Mantém o restante do 687107 intacto, inclusive as correções já validadas.
exec(compile(_source, str(Path(__file__)), "exec"))