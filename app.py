from pathlib import Path
import re

_original = Path(__file__).with_name("app_original.py")
_source = _original.read_text(encoding="utf-8")

_old = re.search(r"def rebuild_product_stats\(.*?\ndef find_product", _source, flags=re.S)
_new = '''def rebuild_product_stats(products):
    items=db("itens_compra",params={"select":"produto_id,compra_id,preco_unitario,quantidade,criado_em"})
    grouped={}
    for x in items:
        if x.get("produto_id") is not None:
            grouped.setdefault(str(x["produto_id"]),[]).append(x)
    updated=0
    for p in products:
        rows=grouped.get(str(p.get("id")),[])
        if not rows:
            db("produtos","PATCH",params={"id":f"eq.{p['id']}"},data={"ultimo_preco":0,"preco_medio":0,"menor_preco":0,"maior_preco":0,"ultima_quantidade":1,"quantidade_compras":0,"atualizado_em":now()})
            updated+=1
            continue
        valid=[x for x in rows if num(x.get("preco_unitario"))>0]
        prices=[num(x.get("preco_unitario")) for x in valid]
        latest=sorted(rows,key=lambda x:str(x.get("criado_em","")))[-1]
        db("produtos","PATCH",params={"id":f"eq.{p['id']}"},data={"ultimo_preco":num(latest.get("preco_unitario")),"preco_medio":sum(prices)/len(prices) if prices else 0,"menor_preco":min(prices) if prices else 0,"maior_preco":max(prices) if prices else 0,"ultima_quantidade":num(latest.get("quantidade")) or 1,"quantidade_compras":len({str(x.get("compra_id")) for x in rows}),"atualizado_em":now()})
        updated+=1
    clear()
    return updated
def find_product'''
if not _old:
    raise RuntimeError("rebuild_product_stats não encontrado")
_source=_source[:_old.start()]+_new+_source[_old.end():]

_old=re.search(r"def delete_history_purchase\(pid\):.*?\ndef parse_history",_source,flags=re.S)
_new='''def delete_history_purchase(pid):
    db("itens_compra","DELETE",params={"compra_id":f"eq.{pid}"})
    db("compras","DELETE",params={"id":f"eq.{pid}"})
    rebuild_product_stats(get_products())
    clear()
def parse_history'''
if not _old:
    raise RuntimeError("delete_history_purchase não encontrado")
_source=_source[:_old.start()]+_new+_source[_old.end():]

_old='''def stage_history(uploaded,products):
    rows=parse_history(uploaded); exact=[]; unmatched=[]
'''
_new='''def stage_history(uploaded,products):
    for k in list(st.session_state.keys()):
        if str(k).startswith(("hist_action_","hist_dest_","hist_cat_","hist_unit_")):
            st.session_state.pop(k,None)
    rows=parse_history(uploaded); exact=[]; unmatched=[]
'''
if _old not in _source:
    raise RuntimeError("stage_history não encontrado")
_source=_source.replace(_old,_new,1)

_old='''    st.session_state["pending_history"]={"exact":exact,"unmatched":unmatched}
'''
_new='''    st.session_state["pending_history"]={"exact":exact,"unmatched":unmatched,"source_count":len(rows),"consolidated_count":len(exact)+len(unmatched)}
'''
if _old not in _source:
    raise RuntimeError("pending_history não encontrado")
_source=_source.replace(_old,_new,1)

_old='''    st.write("Foram encontrados itens que não estão cadastrados. Você pode decidir item a item ou aplicar uma decisão geral.")
'''
_new='''    source_count=pending.get("source_count",len(pending.get("exact",[]))+len(pending.get("unmatched",[])))
    consolidated_count=pending.get("consolidated_count",len(pending.get("exact",[]))+len(pending.get("unmatched",[])))
    st.info(f"Carga: {source_count} linhas do Excel → {consolidated_count} itens após consolidação. Nenhum item é descartado automaticamente.")
    st.write("Foram encontrados itens que não estão cadastrados. Você pode decidir item a item ou aplicar uma decisão geral.")
'''
if _old not in _source:
    raise RuntimeError("texto da revisão não encontrado")
_source=_source.replace(_old,_new,1)

_old=re.search(r"def finish\(items,budget\):.*?\ndef delete_history_purchase",_source,flags=re.S)
_new='''def finish(items,budget):
    if num(budget)<=0:
        raise RuntimeError("Informe o orçamento da compra antes de finalizar.")
    if not items:
        raise RuntimeError("Adicione pelo menos um item antes de finalizar.")
    if any(not x.get("confirmado") for x in items):
        raise RuntimeError("Confirme o preço de todos os itens antes de finalizar.")
    est=sum(num(x.get("quantidade"))*num(x.get("preco_estimado")) for x in items)
    real=sum(num(x.get("quantidade"))*num(x.get("preco_unitario")) for x in items)
    created=db("compras","POST",data={"orcamento":num(budget),"valor_estimado":est,"valor_real":real,"saldo":num(budget)-real,"quantidade_itens":len(items),"data_compra":now()})
    if not created:
        raise RuntimeError("Não foi possível registrar a compra.")
    c=created[0]
    rows=[]
    for x in items:
        q=num(x.get("quantidade")); e=num(x.get("preco_estimado")); p=num(x.get("preco_unitario"))
        pid=create_product(x["nome_produto"],x.get("categoria","Mercearia"),x.get("unidade","un."),p or e,q)
        rows.append({"compra_id":c["id"],"produto_id":pid,"nome_produto":x["nome_produto"],"quantidade":q,"unidade":x.get("unidade","un."),"preco_estimado":e,"preco_unitario":p,"valor_total":q*p,"ultimo_preco":e,"variacao_preco":p-e,"confirmado":True})
    if rows:
        db("itens_compra","POST",data=rows)
        for pid in {x["produto_id"] for x in rows}:
            product_stats(pid)
    db("lista_atual","DELETE",params={"id":"gt.0"})
    save_budget(0)
def delete_history_purchase'''
if not _old:
    raise RuntimeError("finish não encontrado")
_source=_source[:_old.start()]+_new+_source[_old.end():]

_insert='''@st.dialog("Definir orçamento da compra")
def budget_dialog(action):
    st.markdown("### Nova compra")
    st.caption("Informe quanto você pretende gastar. Esse valor ficará vinculado à compra até ela ser finalizada.")
    value=st.number_input("Orçamento disponível",min_value=0.01,value=0.01,step=10.00,format="%.2f",key="new_purchase_budget")
    a,b=st.columns(2)
    if a.button("Cancelar",use_container_width=True):
        st.rerun()
    if b.button("Iniciar compra",type="primary",use_container_width=True):
        save_budget(value)
        if action=="add":
            st.session_state["open_add_after_budget"]=True
        else:
            st.session_state["open_standard_after_budget"]=True
        st.rerun()

'''
marker='@st.dialog("Adicionar produto à lista de compras")\ndef add_list_dialog'
if marker not in _source:
    raise RuntimeError("add_list_dialog não encontrado")
_source=_source.replace(marker,_insert+marker,1)

_old=re.search(r"with buy:\n.*?(?=with prod:\n)",_source,flags=re.S)
_new='''with buy:
    st.subheader("Lista de compras")
    a,b=st.columns(2)

    with a:
        if st.button("Adicionar produto à lista de compras",type="primary",use_container_width=True,key="open_add_list"):
            if not current and budget<=0:
                budget_dialog("add")
            else:
                add_list_dialog(products)

    with b:
        if st.button("Importar lista padrão",use_container_width=True,key="import_standard"):
            if not current and budget<=0:
                budget_dialog("standard")
            else:
                try:
                    rec={}; qs={}
                    for hp in history:
                        seen=set()
                        for x in db("itens_compra",params={"select":"nome_produto,quantidade","compra_id":f"eq.{hp['id']}"}):
                            k=norm(x.get("nome_produto"))
                            if k and k not in seen:
                                seen.add(k); rec[k]=rec.get(k,0)+1; qs.setdefault(k,[]).append(num(x.get("quantidade")))
                    by={norm(p.get("nome")):p for p in products}; added=0
                    for k,cnt in rec.items():
                        if cnt>=2 and k in by and not any(norm(x.get("nome_produto"))==k for x in current):
                            p=by[k]; add_item(p["nome"],p.get("categoria","Mercearia"),p.get("unidade","un."),round(sum(qs[k])/len(qs[k]),2),num(p.get("ultimo_preco"))); added+=1
                    st.success(f"{added} produtos recorrentes adicionados."); st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    if st.session_state.pop("open_add_after_budget",False):
        add_list_dialog(products)

    if st.session_state.pop("open_standard_after_budget",False):
        rec={}; qs={}
        for hp in history:
            seen=set()
            for x in db("itens_compra",params={"select":"nome_produto,quantidade","compra_id":f"eq.{hp['id']}"}):
                k=norm(x.get("nome_produto"))
                if k and k not in seen:
                    seen.add(k); rec[k]=rec.get(k,0)+1; qs.setdefault(k,[]).append(num(x.get("quantidade")))
        by={norm(p.get("nome")):p for p in products}; added=0
        for k,cnt in rec.items():
            if cnt>=2 and k in by and not any(norm(x.get("nome_produto"))==k for x in current):
                p=by[k]; add_item(p["nome"],p.get("categoria","Mercearia"),p.get("unidade","un."),round(sum(qs[k])/len(qs[k]),2),num(p.get("ultimo_preco"))); added+=1
        if added:
            st.success(f"{added} produtos recorrentes adicionados."); st.rerun()
        else:
            st.info("Não há produtos recorrentes suficientes para montar a lista padrão.")

    if not current:
        st.markdown('<div class="empty"><strong>Sua lista está vazia.</strong><br>Ao iniciar uma nova compra, o sistema solicitará o orçamento antes do primeiro item.</div>',unsafe_allow_html=True)

    for item in current:
        ok=bool(item.get("confirmado")); total=num(item.get("quantidade"))*num(item.get("preco_estimado"))
        st.markdown('<div class="card">',unsafe_allow_html=True)
        a,b=st.columns([4,1])
        with a:
            st.markdown(f'<div class="product-name {"done" if ok else ""}">{item["nome_produto"]}</div><div class="muted">{item.get("categoria","Mercearia")} · {num(item.get("quantidade")):g} {item.get("unidade","un.")}</div>',unsafe_allow_html=True)
        with b:
            st.markdown('<span class="pill">✓ Confirmado</span>' if ok else f'<div style="text-align:right;font-weight:700">{money(total)}</div>',unsafe_allow_html=True)
        c1,c2,c3=st.columns([1.2,1.3,1])
        with c1:
            q=st.number_input("Qtd",min_value=.001,value=num(item.get("quantidade")) or 1.,step=1.,key=f"q{item['id']}",disabled=ok)
            if q!=num(item.get("quantidade")) and not ok:
                edit_item(item["id"],quantidade=q); st.rerun()
        with c2:
            st.caption("Preço estimado"); st.write(money(item.get("preco_estimado")))
        with c3:
            if not ok:
                if st.button("Confirmar",type="primary",key=f"c{item['id']}",use_container_width=True):
                    st.session_state["confirm_item"]=item; st.rerun()
            else:
                st.caption("Preço pago"); st.write(money(item.get("preco_unitario")))
        d1,d2=st.columns([3,1])
        with d1:
            st.caption(f"Total pago: {money(num(item.get('quantidade'))*num(item.get('preco_unitario')))}" if ok else "Aguardando confirmação do preço")
        with d2:
            if st.button("Excluir",key=f"d{item['id']}",use_container_width=True):
                remove_item(item["id"]); st.rerun()
        st.markdown('</div>',unsafe_allow_html=True)

    if current:
        st.divider()
        f1,f2=st.columns([2,1])
        with f1:
            st.caption(f"Compra em andamento · Orçamento: {money(budget)} · Confirmado: {done}/{len(current)} itens")
        with f2:
            if st.button("Finalizar compra",type="primary",disabled=(budget<=0 or done<len(current)),use_container_width=True,key="finish_purchase"):
                try:
                    finish(current,budget); st.success("Compra finalizada e registrada no histórico."); st.rerun()
                except Exception as e:
                    st.error(f"Erro ao finalizar: {e}")

'''
if not _old:
    raise RuntimeError("aba Compra não encontrada")
_source=_source[:_old.start()]+_new+_source[_old.end():]

_old=re.search(r"with ana:\n.*?(?=with config:)",_source,flags=re.S)
_new='''with ana:
    st.subheader("Análises")
    st.caption("Visão gerencial das compras, gastos, preços e principais desvios.")
    if history:
        all_items=[]
        for hp in history:
            for xi in db("itens_compra",params={"select":"*","compra_id":f"eq.{hp['id']}"}):
                all_items.append({**xi,"categoria":next((pp.get("categoria","Sem categoria") for pp in products if str(pp.get("id"))==str(xi.get("produto_id"))),"Sem categoria")})
        total_real=sum(num(x.get("valor_total")) for x in all_items)
        total_est=sum(num(x.get("preco_estimado"))*num(x.get("quantidade")) for x in all_items)
        economia=total_est-total_real; qtd_itens=sum(num(x.get("quantidade")) for x in all_items); ticket=total_real/len(history)
        variacoes=[num(x.get("variacao_preco")) for x in all_items if num(x.get("preco_unitario"))>0 and num(x.get("ultimo_preco"))>0]
        aumentos=sum(v>0.0001 for v in variacoes); reducoes=sum(v<-0.0001 for v in variacoes); estaveis=len(variacoes)-aumentos-reducoes
        st.markdown("### Visão geral")
        k1,k2,k3,k4,k5=st.columns(5)
        k1.metric("Gasto acumulado",money(total_real)); k2.metric("Compras realizadas",len(history)); k3.metric("Itens comprados",f"{qtd_itens:g}"); k4.metric("Ticket médio",money(ticket)); k5.metric("Economia vs. estimativa",money(economia))
        if total_est:
            if economia>=0: st.success(f"Leitura rápida: gasto realizado {money(economia)} abaixo da estimativa.")
            else: st.warning(f"Leitura rápida: gasto realizado {money(abs(economia))} acima da estimativa.")
        else:
            st.info("Leitura rápida: não há estimativa suficiente para calcular a economia.")
        t1,t2,t3=st.tabs(["Desempenho financeiro","Onde está o gasto","Preços e oportunidades"])
        with t1:
            st.markdown("#### Estimado × realizado por compra")
            comp_df=pd.DataFrame([{"Compra":f"Compra {i+1}","Estimado":num(hp.get("valor_estimado")),"Real":num(hp.get("valor_real"))} for i,hp in enumerate(history)])
            st.bar_chart(comp_df.set_index("Compra"),use_container_width=True)
            resumo=pd.DataFrame([{"Data":str(hp.get("data_compra",""))[:16].replace("T"," "),"Orçamento":money(hp.get("orcamento")),"Estimado":money(hp.get("valor_estimado")),"Real":money(hp.get("valor_real")),"Saldo":money(hp.get("saldo")),"Itens":int(num(hp.get("quantidade_itens")))} for hp in history])
            st.dataframe(resumo,use_container_width=True,hide_index=True)
        with t2:
            cat={}
            for x in all_items: cat[x["categoria"]]=cat.get(x["categoria"],0)+num(x.get("valor_total"))
            cat_df=pd.DataFrame(sorted(cat.items(),key=lambda z:z[1],reverse=True),columns=["Categoria","Gasto"])
            if not cat_df.empty:
                st.markdown("#### Gasto por categoria"); st.bar_chart(cat_df.set_index("Categoria"),use_container_width=True)
            prodg={}
            for x in all_items:
                name=x.get("nome_produto","Produto"); prodg[name]=prodg.get(name,0)+num(x.get("valor_total"))
            top=pd.DataFrame(sorted(prodg.items(),key=lambda z:z[1],reverse=True)[:10],columns=["Produto","Gasto"])
            if not top.empty:
                st.markdown("#### Top 10 produtos por impacto financeiro"); st.bar_chart(top.set_index("Produto"),use_container_width=True)
        with t3:
            p1,p2,p3,p4=st.columns(4)
            p1.metric("Preços aumentaram",aumentos); p2.metric("Preços reduziram",reducoes); p3.metric("Sem alteração",estaveis); p4.metric("Com comparação",len(variacoes))
            price_rows=[]
            for x in all_items:
                old=num(x.get("ultimo_preco")); new=num(x.get("preco_unitario")); q=num(x.get("quantidade"))
                if old>0 and new>0:
                    price_rows.append({"Produto":x.get("nome_produto"),"Último preço":money(old),"Preço pago":money(new),"Variação":money(new-old),"Variação %":(new-old)/old,"Qtd":q})
            if price_rows:
                pdf=pd.DataFrame(price_rows).sort_values("Variação %",ascending=False)
                pdf["Variação %"]=pdf["Variação %"].map(lambda v:f"{v:+.1%}")
                st.dataframe(pdf,use_container_width=True,hide_index=True)
            else:
                st.info("Ainda não existem comparações suficientes de preços.")
    else:
        st.markdown('<div class="empty"><strong>Nenhum dado histórico disponível.</strong><br>Finalize uma compra para liberar os indicadores gerenciais.</div>',unsafe_allow_html=True)

'''
if not _old:
    raise RuntimeError("aba Análises não encontrada")
_source=_source[:_old.start()]+_new+_source[_old.end():]

_old='''            n,total,created,ignored=commit_history(pending,ga); st.success(f"{n} itens importados. {created} produto(s) novo(s). {ignored} item(ns) ignorado(s). Total: {money(total)}"); st.rerun()
'''
_new='''            n,total,created,ignored=commit_history(pending,ga)
            origem=pending.get("source_count",n); consolidados=pending.get("consolidated_count",n)
            st.success(f"{origem} linhas lidas → {consolidados} itens após consolidação → {n} importados. {created} produto(s) novo(s). {ignored} item(ns) ignorado(s). Total: {money(total)}")
            st.rerun()
'''
if _old in _source:
    _source=_source.replace(_old,_new,1)

exec(compile(_source,str(_original),"exec"),globals(),globals())
