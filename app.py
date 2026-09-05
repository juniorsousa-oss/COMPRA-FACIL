from pathlib import Path

# Executa a versão original, mas aplica correções de forma segura antes de iniciar o Streamlit.
_original = Path(__file__).with_name("app_original.py")
_source = _original.read_text(encoding="utf-8")

# Cada nova carga deve começar sem decisões antigas dos widgets de revisão.
_old_stage = '''def stage_history(uploaded,products):\n    rows=parse_history(uploaded); exact=[]; unmatched=[]\n'''
_new_stage = '''def stage_history(uploaded,products):\n    # Limpa decisões antigas do Streamlit para que uma nova carga nunca herde\n    # ações de uma importação anterior com outra quantidade/ordem de itens.\n    for k in list(st.session_state.keys()):\n        if str(k).startswith(("hist_action_","hist_dest_","hist_cat_","hist_unit_")):\n            st.session_state.pop(k,None)\n    rows=parse_history(uploaded); exact=[]; unmatched=[]\n'''
if _old_stage not in _source:
    raise RuntimeError("Não foi possível localizar stage_history para aplicar a correção.")
_source = _source.replace(_old_stage, _new_stage, 1)

_old_pending = '''    st.session_state["pending_history"]={"exact":exact,"unmatched":unmatched}\n'''
_new_pending = '''    st.session_state["pending_history"]={\n        "exact":exact,\n        "unmatched":unmatched,\n        "source_count":len(rows),\n        "consolidated_count":len(exact)+len(unmatched),\n    }\n'''
if _old_pending not in _source:
    raise RuntimeError("Não foi possível localizar pending_history para aplicar a correção.")
_source = _source.replace(_old_pending, _new_pending, 1)

_old_info = '''    st.write("Foram encontrados itens que não estão cadastrados. Você pode decidir item a item ou aplicar uma decisão geral.")\n'''
_new_info = '''    source_count=pending.get("source_count",len(pending.get("exact",[]))+len(pending.get("unmatched",[])))\n    consolidated_count=pending.get("consolidated_count",len(pending.get("exact",[]))+len(pending.get("unmatched",[])))\n    st.info(f"Carga: {source_count} linhas do Excel → {consolidated_count} itens após consolidação. Nenhum item é descartado automaticamente.")\n    st.write("Foram encontrados itens que não estão cadastrados. Você pode decidir item a item ou aplicar uma decisão geral.")\n'''
if _old_info not in _source:
    raise RuntimeError("Não foi possível localizar o texto da revisão.")
_source = _source.replace(_old_info, _new_info, 1)

_old_success = '''            n,total,created,ignored=commit_history(pending,ga); st.success(f"{n} itens importados. {created} produto(s) novo(s). {ignored} item(ns) ignorado(s). Total: {money(total)}"); st.rerun()\n'''
_new_success = '''            n,total,created,ignored=commit_history(pending,ga)\n            origem=pending.get("source_count",n)\n            consolidados=pending.get("consolidated_count",n)\n            st.success(f"{origem} linhas lidas → {consolidados} itens após consolidação → {n} importados. {created} produto(s) novo(s). {ignored} item(ns) ignorado(s). Total: {money(total)}")\n            st.rerun()\n'''
if _old_success not in _source:
    raise RuntimeError("Não foi possível localizar a mensagem final da importação.")
_source = _source.replace(_old_success, _new_success, 1)

exec(compile(_source, str(_original), "exec"), globals(), globals())
