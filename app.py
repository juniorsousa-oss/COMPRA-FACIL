from pathlib import Path
import urllib.request

# Carrega a versão que contém a exportação de produtos sem preço.
BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/c8f65e0243d4fc2ff1dec0e0d186eec161f52f21/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

# O erro vinha do Path.read_text: em reruns do Streamlit, a função salva como
# "original" podia na verdade ser um patch de uma execução anterior. Isso fazia
# um _patched_read_text chamar outro _patched_read_text e o mesmo app_original
# era transformado mais de uma vez.
#
# Em vez de depender de Path.read_text, fazemos a leitura-base diretamente com
# io.open. Assim a transformação do app_original acontece uma única vez e não
# depende do estado deixado por reruns anteriores.
_old_safe_reader = '''_new_reader = \'\'\'_original_read_text = getattr(Path, "_compra_facil_original_read_text", Path.read_text)
if not hasattr(Path, "_compra_facil_original_read_text"):
    Path._compra_facil_original_read_text = _original_read_text\'\'\''''

_new_safe_reader = '''_new_reader = \'\'\'import io as _path_io
def _original_read_text(self, *args, **kwargs):
    _encoding = kwargs.get("encoding", args[0] if len(args) > 0 else None)
    _errors = kwargs.get("errors", args[1] if len(args) > 1 else None)
    _newline = kwargs.get("newline", args[2] if len(args) > 2 else None)
    with _path_io.open(self, mode="r", encoding=_encoding, errors=_errors, newline=_newline) as _file:
        return _file.read()\'\'\''''

if _old_safe_reader not in source:
    raise RuntimeError("Ponto de correção segura do leitor não encontrado.")
source = source.replace(_old_safe_reader, _new_safe_reader, 1)

exec(compile(source, str(Path(__file__)), "exec"))
