from pathlib import Path
import urllib.request

_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O 687107 carrega o 0074, que por sua vez carrega app_original.py.
# Corrige somente o ponto em que o 0074 lê o app_original.py.
_loader = '_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")'
_nested_read = '_source = _original.read_text(encoding="utf-8")'
_nested_fix = '_source = _original.read_text(encoding="utf-8")\n_source = _source.replace("with hist:", "with st.container():", 1)'
_source = _source.replace(_loader, _loader + '\n_source = _source.replace(' + repr(_nested_read) + ', ' + repr(_nested_fix) + ', 1)', 1)

exec(compile(_source, str(Path(__file__)), "exec"))