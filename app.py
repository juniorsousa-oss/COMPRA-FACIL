from pathlib import Path
import re
import urllib.request

# Usa a versão estável que já contém os ajustes anteriores.
_BASE_URL = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/0074e6f1fe2b4bfdee87793c6bff1fec391d35cc/app.py"
_source = urllib.request.urlopen(_BASE_URL, timeout=10).read().decode("utf-8")

# Em itens confirmados, substitui o botão desabilitado por Desconfirmar.
_old = '''        with d1:\n            st.button("Confirmado",disabled=True,use_container_width=True,key=f"c_done_{item['id']}") if ok else None\n            if not ok and st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True): st.session_state["confirm_item"]=item; st.rerun()\n'''
_new = '''        with d1:\n            if ok:\n                if st.button("Desconfirmar",use_container_width=True,key=f"unconfirm_{item['id']}"):\n                    edit_item(item["id"],confirmado=False)\n                    st.rerun()\n            else:\n                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True):\n                    st.session_state["confirm_item"]=item\n                    st.rerun()\n'''
if _old not in _source:
    raise RuntimeError("Bloco do botão de confirmação não encontrado.")
_source = _source.replace(_old, _new, 1)

# Executa o app já corrigido.
exec(compile(_source, str(Path(__file__)), "exec"))
