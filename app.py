from pathlib import Path
import re
import urllib.request

# Mantém toda a versão estável atual e aplica somente o novo ajuste no fluxo de confirmação.
_BASE_URL = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/0074e6f1fe2b4bfdee87793c6bff1fec391d35cc/app.py"
_base = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")

# Insere a possibilidade de voltar um item confirmado para "A confirmar".
_patch = r'''_source = re.sub(r"        with d1:\n.*?(?=        with d2:)", '''        with d1:\n            if ok:\n                if st.button("Desconfirmar",use_container_width=True,key=f"unconfirm_{item['id']}"):\n                    edit_item(item["id"],confirmado=False)\n                    st.rerun()\n            else:\n                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True):\n                    st.session_state["confirm_item"]=item\n                    st.rerun()\n''', _source, count=1, flags=re.S)
'''

# Executa o app estável após inserir o novo comportamento, sem alterar os demais fluxos.
_idx = _base.rfind("exec(")
if _idx < 0:
    raise RuntimeError("Ponto de execução do app não encontrado.")
_base = _base[:_idx] + _patch + "\n" + _base[_idx:]
exec(compile(_base, str(Path(__file__)), "exec"))
