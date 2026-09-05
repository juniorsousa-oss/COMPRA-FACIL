from pathlib import Path
import re

# Executa a versão original, mas aplica correções de forma segura antes de iniciar o Streamlit.
_original = Path(__file__).with_name("app_original.py")
_source = _original.read_text(encoding="utf-8")

# Recalcula TODOS os indicadores dos produtos a partir do histórico atual.
# Se um produto não possui mais itens no histórico, seus indicadores voltam a zero.
_old_rebuild = re.search(r"def rebuild_product_stats\(.*?\ndef find_product", _source, flags=re.S)
if not _old_rebuild:
    raise RuntimeError("Não foi possível localizar rebuild_product_stats para aplicar a correção.")
_new_rebuild = '''def rebuild_product_stats(products):
    items=db("itens_compra",params={"select":"produto_id,compra_id,preco_unitario,quantidade,criado_em"}); grouped={}
    for x in items:
        if x.get("produto_id") is not None: grouped.setdefault(str(x["produto_id"]),[]).append(x)
    updated=0
    for p in products:
        rows=grouped.get(str(p.get("id")),[])
        if not rows:
            db("produtos","PATCH",params={"id":f"eq.{p['id']}"},data={"ultimo_preco":0,"preco_medio":0,"menor_preco":0,"maior_preco":0,"ultima_quantidade":1,"quantidade_compras":0,"atualizado_em":now()})
            updated+=1
            continue
        valid=[x for x in rows if num(x.get("preco_unitario"))>0]; prices=[num(x.get("preco_unitario")) for x in valid]; latest=sorted(rows,key=lambda x:str(x.get("criado_em","")))[-1]
        db("produtos","PATCH",params={"id":f"eq.{p['id']}"},data={"ultimo_preco":num(latest.get("preco_unitario")),"preco_medio":sum(prices)/len(prices) if prices else 0,"menor_preco":min(prices) if prices else 0,"maior_preco":max(prices) if prices else 0,"ultima_quantidade":num(latest.get("quantidade")) or 1,"quantidade_compras":len({str(x.get("compra_id")) for x in rows}),"atualizado_em":now()}); updated+=1
    clear(); return updated
def find_product'''
_source = _source[:_old_rebuild.start()] + _new_rebuild + _source[_old_rebuild.end():]

# Ao excluir qualquer compra, os indicadores dos produtos são reconstruídos imediatamente.
_old_delete = re.search(r"def delete_history_purchase\(pid\):.*?\ndef parse_history", _source, flags=re.S)
if not _old_delete:
    raise RuntimeError("Não foi possível localizar delete_history_purchase para aplicar a correção.")
_new_delete = '''def delete_history_purchase(pid):
    db("itens_compra","DELETE",params={"compra_id":f"eq.{pid}"}); db("compras","DELETE",params={"id":f"eq.{pid}"}); rebuild_product_stats(get_products()); clear()
def parse_history'''
_source = _source[:_old_delete.start()] + _new_delete + _source[_old_delete.end():]

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