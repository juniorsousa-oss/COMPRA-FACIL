from pathlib import Path
import urllib.request

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/e207deca8b264ae72fe4f8b8a48a9b49e50b9847/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

# No tratamento de duplicidade do commit-base, st.stop() interrompia toda
# a renderização da página. Assim os cards já existentes deixavam de ser
# desenhados até o próximo rerun. Mantemos a trava de duplicidade, mas
# retornamos apenas da função add_item, sem interromper o restante da tela.
needle = "        st.stop()"
count = source.count(needle)
if count < 2:
    raise RuntimeError("Tratamento de duplicidade esperado não foi encontrado.")
source = source.replace(needle, "        return", 2)

exec(compile(source, str(Path(__file__)), "exec"))
