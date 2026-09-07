from pathlib import Path
import urllib.request

# Voltamos à versão que já tinha a Próxima lista funcionando.
_BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
_source = urllib.request.urlopen(_BASE, timeout=10).read().decode("utf-8")

# O bloqueio de duplicidade continua existindo, mas não pode derrubar o Streamlit.
_old = '''        raise RuntimeError(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")'''
_new = '''        st.warning(f"O produto **{name.strip()}** já está nesta lista. Altere a quantidade no item já adicionado.")
        return False'''
_source = _source.replace(_old, _new, 1)

# Se a inclusão foi recusada, não executa rerun e mantém o aviso visível.
_old_ui = '''                    add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))); st.rerun()'''
_new_ui = '''                    if add_item(selected,p.get("categoria","Mercearia"),p.get("unidade","un."),qty,num(p.get("ultimo_preco"))):
                        st.rerun()'''
_source = _source.replace(_old_ui, _new_ui, 1)

exec(compile(_source, str(Path(__file__)), "exec"))
