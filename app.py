from pathlib import Path
import re

# Executa a versão original, aplicando correções e uma camada de análise profissional.
_original = Path(__file__).with_name("app_original.py")
_source = _original.read_text(encoding="utf-8")

# Recalcula TODOS os indicadores dos produtos a partir do histórico atual.
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

_old_delete = re.search(r"def delete_history_purchase\(pid\):.*?\ndef parse_history", _source, flags=re.S)
if not _old_delete:
    raise RuntimeError("Não foi possível localizar delete_history_purchase para aplicar a correção.")
_new_delete = '''def delete_history_purchase(pid):
    db("itens_compra","DELETE",params={"compra_id":f"eq.{pid}"}); db("compras","DELETE",params={"id":f"eq.{pid}"}); rebuild_product_stats(get_products()); clear()
def parse_history'''
_source = _source[:_old_delete.start()] + _new_delete + _source[_old_delete.end():]

_old_stage = '''def stage_history(uploaded,products):\n    rows=parse_history(uploaded); exact=[]; unmatched=[]\n'''
_new_stage = '''def stage_history(uploaded,products):\n    for k in list(st.session_state.keys()):\n        if str(k).startswith(("hist_action_","hist_dest_","hist_cat_","hist_unit_")):\n            st.session_state.pop(k,None)\n    rows=parse_history(uploaded); exact=[]; unmatched=[]\n'''
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

_old_ana = re.search(r'with ana:\n    st\.subheader\("Análises"\).*?(?=with config:)', _source, flags=re.S)
if not _old_ana:
    raise RuntimeError("Não foi possível localizar a aba Análises.")
_new_ana = '''with ana:
    st.subheader("Análises")
    st.caption("Visão gerencial das compras, gastos, preços e principais desvios.")
    if history:
        all_items=[]
        for hp in history:
            for xi in db("itens_compra",params={"select":"*","compra_id":f"eq.{hp['id']}"}):
                all_items.append({**xi,"data_compra":hp.get("data_compra"),"categoria":next((pp.get("categoria","Sem categoria") for pp in products if str(pp.get("id"))==str(xi.get("produto_id"))),"Sem categoria")})
        total_real=sum(num(x.get("valor_total")) for x in all_items)
        total_est=sum(num(x.get("preco_estimado"))*num(x.get("quantidade")) for x in all_items)
        economia=total_est-total_real
        qtd_itens=sum(num(x.get("quantidade")) for x in all_items)
        ticket=total_real/len(history) if history else 0
        compras_com_desvio=sum(1 for hp in history if num(hp.get("valor_estimado"))>0 and num(hp.get("valor_real"))>num(hp.get("valor_estimado")))
        price_rows=[]
        for x in all_items:
            old=num(x.get("ultimo_preco")); new=num(x.get("preco_unitario")); q=num(x.get("quantidade"))
            if old>0 and new>0:
                price_rows.append({"Produto":x.get("nome_produto"),"Último preço":old,"Preço pago":new,"Variação":new-old,"Variação %":(new-old)/old,"Qtd":q})
        aumentos=sum(1 for x in price_rows if x["Variação"]>0.0001)
        reducoes=sum(1 for x in price_rows if x["Variação"]<-0.0001)
        estaveis=len(price_rows)-aumentos-reducoes

        st.markdown("### Visão geral")
        k1,k2,k3,k4,k5=st.columns(5)
        k1.metric("Gasto acumulado",money(total_real))
        k2.metric("Compras realizadas",f"{len(history)}")
        k3.metric("Itens comprados",f"{qtd_itens:g}")
        k4.metric("Ticket médio",money(ticket))
        k5.metric("Economia vs. estimativa",money(economia),delta=("economia" if economia>=0 else "acima da estimativa"),delta_color=("normal" if economia>=0 else "inverse"))

        if economia>=0:
            texto=f"**Leitura rápida:** o gasto realizado está {money(economia)} abaixo da estimativa histórica. Isso representa {economia/total_est:.1%} de economia sobre o valor estimado." if total_est else "**Leitura rápida:** não há base de estimativa suficiente para calcular a economia percentual."
            st.success(texto)
        else:
            st.warning(f"**Leitura rápida:** o gasto realizado ficou {money(abs(economia))} acima da estimativa histórica.")

        t1,t2,t3=st.tabs(["Desempenho financeiro","Onde está o gasto","Preços e oportunidades"])
        with t1:
            st.markdown("#### Comparativo por compra")
            comp_df=pd.DataFrame([{"Compra":f"Compra {i+1}","Estimado":num(hp.get("valor_estimado")),"Real":num(hp.get("valor_real"))} for i,hp in enumerate(history)])
            st.bar_chart(comp_df.set_index("Compra"),use_container_width=True)
            resumo_df=pd.DataFrame([{"Data":str(hp.get("data_compra",""))[:16].replace("T"," "),"Estimado":money(hp.get("valor_estimado")),"Real":money(hp.get("valor_real")),"Economia":money(num(hp.get("valor_estimado"))-num(hp.get("valor_real"))),"Itens":int(num(hp.get("quantidade_itens")))} for hp in history])
            st.dataframe(resumo_df,use_container_width=True,hide_index=True)
            c1,c2,c3=st.columns(3)
            c1.metric("Compras acima da estimativa",f"{compras_com_desvio} de {len(history)}")
            c2.metric("Maior compra",money(max((num(hp.get("valor_real")) for hp in history),default=0)))
            c3.metric("Estimativa total",money(total_est))

        with t2:
            st.markdown("#### Distribuição do gasto por categoria")
            cat={}
            for x in all_items: cat[x["categoria"]]=cat.get(x["categoria"],0)+num(x.get("valor_total"))
            cat_df=pd.DataFrame(sorted(cat.items(),key=lambda z:z[1],reverse=True),columns=["Categoria","Gasto"])
            if not cat_df.empty:
                st.bar_chart(cat_df.set_index("Categoria"),use_container_width=True)
                cat_view=cat_df.copy(); cat_view["Participação"]=(cat_view["Gasto"]/total_real).map(lambda v:f"{v:.1%}" if total_real else "0,0%"); cat_view["Gasto"]=cat_view["Gasto"].map(money)
                st.dataframe(cat_view.rename(columns={"Gasto":"Valor gasto"}),use_container_width=True,hide_index=True)
            st.markdown("#### Top 10 produtos por impacto financeiro")
            prod={}
            for x in all_items:
                n=x.get("nome_produto","Produto"); prod[n]=prod.get(n,0)+num(x.get("valor_total"))
            top_df=pd.DataFrame(sorted(prod.items(),key=lambda z:z[1],reverse=True)[:10],columns=["Produto","Gasto"])
            if not top_df.empty:
                st.bar_chart(top_df.set_index("Produto"),use_container_width=True)
                top_view=top_df.copy(); top_view["Participação"]=(top_view["Gasto"]/total_real).map(lambda v:f"{v:.1%}" if total_real else "0,0%"); top_view["Gasto"]=top_view["Gasto"].map(money)
                st.dataframe(top_view.rename(columns={"Gasto":"Valor gasto"}),use_container_width=True,hide_index=True)

        with t3:
            st.markdown("#### Monitoramento de preços")
            p1,p2,p3,p4=st.columns(4)
            p1.metric("Aumentos",f"{aumentos}")
            p2.metric("Reduções",f"{reducoes}")
            p3.metric("Estáveis",f"{estaveis}")
            p4.metric("Comparações",f"{len(price_rows)}")
            if price_rows:
                delta_total=sum(x["Variação"]*x["Qtd"] for x in price_rows)
                if delta_total>0: st.warning(f"Pressão de preços identificada: **{money(delta_total)}** acima dos últimos preços registrados, considerando as quantidades compradas.")
                elif delta_total<0: st.success(f"Redução potencial identificada: **{money(abs(delta_total))}** frente aos últimos preços registrados, considerando as quantidades compradas.")
                pv=pd.DataFrame(price_rows).sort_values("Variação %",ascending=False)
                pv["Último preço"]=pv["Último preço"].map(money); pv["Preço pago"]=pv["Preço pago"].map(money); pv["Variação"]=pv["Variação"].map(money); pv["Variação %"]=pv["Variação %"].map(lambda v:f"{v:+.1%}")
                st.dataframe(pv,use_container_width=True,hide_index=True)
            else:
                st.info("Ainda não existem comparações suficientes de preços para gerar oportunidades de análise.")
    else:
        st.markdown('<div class="empty"><strong>Nenhum dado histórico disponível.</strong><br>Finalize uma compra ou importe um histórico para liberar os indicadores gerenciais.</div>',unsafe_allow_html=True)
'''
_source = _source[:_old_ana.start()] + _new_ana + _source[_old_ana.end():]

exec(compile(_source, str(_original), "exec"), globals(), globals())
