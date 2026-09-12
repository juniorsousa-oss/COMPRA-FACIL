import importlib
import pathlib
import urllib.request

# O Streamlit mantém o mesmo processo entre reruns. Como uma versão anterior
# interceptava Path.read_text, garantimos aqui que cada execução começa com
# uma implementação limpa do pathlib antes de carregar o app.
pathlib = importlib.reload(pathlib)
Path = pathlib.Path

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/c8f65e0243d4fc2ff1dec0e0d186eec161f52f21/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

exec(compile(source, str(Path(__file__)), "exec"))
