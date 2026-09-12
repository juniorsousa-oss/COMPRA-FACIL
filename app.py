from pathlib import Path
import urllib.request

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/5734e4c868a929fbb2fb4a4c3e6824f9638d06e4/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

# O wrapper 5734 intercepta Path.read_text para aplicar o bloco de preço sugerido.
# Em reruns do Streamlit, Path.read_text pode continuar apontando para o patch anterior,
# provocando recursão. Guardamos sempre a implementação original e restauramos ao final.
_old_reader = "_original_read_text = Path.read_text"
_new_reader = '''_original_read_text = getattr(Path, "_compra_facil_original_read_text", Path.read_text)
if not hasattr(Path, "_compra_facil_original_read_text"):
    Path._compra_facil_original_read_text = _original_read_text'''
if _old_reader not in source:
    raise RuntimeError("Ponto de proteção do leitor de arquivo não encontrado.")
source = source.replace(_old_reader, _new_reader, 1)

_old_exec = '''Path.read_text = _patched_read_text

exec(compile(source, str(Path(__file__)), "exec"))'''
_new_exec = '''Path.read_text = _patched_read_text
try:
    exec(compile(source, str(Path(__file__)), "exec"))
finally:
    Path.read_text = _original_read_text'''
if _old_exec not in source:
    raise RuntimeError("Ponto de restauração do leitor de arquivo não encontrado.")
source = source.replace(_old_exec, _new_exec, 1)

# Acrescenta, dentro do expander de preço sugerido, a exportação dos produtos
# que ainda não possuem nem último preço real nem preço sugerido.
_old = '''    with st.expander("Preço sugerido para produtos sem histórico",expanded=False):
        st.caption("Regra usada nas novas listas: primeiro o último preço real; se não existir, o preço sugerido; se ambos estiverem vazios, o produto permanece sem referência.")
        _suggest_names=[p.get("nome","") for p in products if p.get("nome")]
'''

_new = '''    with st.expander("Preço sugerido para produtos sem histórico",expanded=False):
        st.caption("Regra usada nas novas listas: primeiro o último preço real; se não existir, o preço sugerido; se ambos estiverem vazios, o produto permanece sem referência.")

        _sem_preco=[p for p in products if num(p.get("ultimo_preco"))<=0 and num(p.get("preco_sugerido"))<=0]
        if _sem_preco:
            _export_df=pd.DataFrame([{
                "PRODUTO":p.get("nome"),
                "CATEGORIA":p.get("categoria"),
                "UNIDADE":p.get("unidade"),
                "PREÇO SUGERIDO":"",
                "FONTE":""
            } for p in _sem_preco])
            _export_buffer=io.BytesIO()
            with pd.ExcelWriter(_export_buffer,engine="openpyxl") as _writer:
                _export_df.to_excel(_writer,index=False,sheet_name="Produtos sem preço")
                _ws=_writer.book["Produtos sem preço"]
                _ws.freeze_panes="A2"
                _ws.auto_filter.ref=_ws.dimensions
                from openpyxl.styles import Font,PatternFill,Alignment
                for _cell in _ws[1]:
                    _cell.font=Font(bold=True,color="FFFFFF")
                    _cell.fill=PatternFill("solid",fgColor="2F6F5E")
                    _cell.alignment=Alignment(horizontal="center")
                _ws.column_dimensions["A"].width=34
                _ws.column_dimensions["B"].width=22
                _ws.column_dimensions["C"].width=14
                _ws.column_dimensions["D"].width=18
                _ws.column_dimensions["E"].width=34
            _export_buffer.seek(0)
            st.download_button(
                f"Exportar {len(_sem_preco)} produto(s) sem preço",
                data=_export_buffer.getvalue(),
                file_name="produtos_sem_preco.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="export_products_without_price"
            )
            st.caption("O arquivo já sai no mesmo formato aceito pela importação de preços sugeridos. Basta preencher PREÇO SUGERIDO e, se desejar, FONTE.")
        else:
            st.success("Todos os produtos cadastrados já possuem último preço ou preço sugerido.")

        _suggest_names=[p.get("nome","") for p in products if p.get("nome")]
'''

if _old not in source:
    raise RuntimeError("Bloco de preço sugerido para exportação não encontrado.")
source = source.replace(_old,_new,1)

exec(compile(source, str(Path(__file__)), "exec"))
