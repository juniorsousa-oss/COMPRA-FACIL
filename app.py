from pathlib import Path
import urllib.request
import streamlit as st

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/687107340a7df519efc6f6f849dbfcb8707968e9/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

safe_add = '''def add_item(name,cat,unit,qty,price):
    existing=db("lista_atual",params={"select":"id,nome_produto"})
    if any(norm(x.get("nome_produto"))==norm(name) for x in existing):
        st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
        st.stop()
    try:
        db("lista_atual","POST",data={"nome_produto":name.strip(),"categoria":cat,"unidade":unit or "un.","quantidade":num(qty),"preco_estimado":num(price),"preco_unitario":0,"confirmado":False,"atualizado_em":now()})
    except RuntimeError as e:
        if "23505" in str(e):
            st.warning(f"O produto '{name.strip()}' já está nesta lista. Altere a quantidade no item já adicionado.")
            st.stop()
        raise
    clear()
'''

next_helpers = '''def move_item_to_next_list(item_id):
    rows=db("lista_atual",params={"select":"*","id":f"eq.{item_id}"})
    if not rows:
        return False
    item=rows[0]
    pending=db("lista_proxima",params={"select":"*"})
    same=next((p for p in pending if norm(p.get("nome_produto"))==norm(item.get("nome_produto"))),None)
    if same:
        new_qty=num(same.get("quantidade"))+num(item.get("quantidade"))
        db("lista_proxima","PATCH",params={"id":f"eq.{same['id']}"},data={"quantidade":new_qty,"preco_estimado":num(same.get("preco_estimado")) or num(item.get("preco_estimado")),"atualizado_em":now()})
    else:
        db("lista_proxima","POST",data={"nome_produto":item.get("nome_produto"),"categoria":item.get("categoria","Mercearia"),"unidade":item.get("unidade","un."),"quantidade":num(item.get("quantidade")),"preco_estimado":num(item.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now()})
    db("lista_atual","DELETE",params={"id":f"eq.{item_id}"})
    clear()
    return True

def restore_next_list():
    pending=db("lista_proxima",params={"select":"*","order":"id.asc"})
    if not pending:
        return 0
    rows=[{"nome_produto":x.get("nome_produto"),"categoria":x.get("categoria","Mercearia"),"unidade":x.get("unidade","un."),"quantidade":num(x.get("quantidade")),"preco_estimado":num(x.get("preco_estimado")),"preco_unitario":0,"confirmado":False,"criado_em":now(),"atualizado_em":now()} for x in pending]
    db("lista_atual","POST",data=rows)
    db("lista_proxima","DELETE",params={"id":"gt.0"})
    clear()
    return len(rows)

'''

professional_analysis = '''with ana:
    st.subheader("Análises")
    st.caption("Visão gerencial de gastos, aderência ao orçamento, evolução de preços e concentração de consumo.")
    if not history:
        st.markdown('<div class="empty">Finalize uma compra para gerar análises.</div>',unsafe_allow_html=True)
    else:
        hist_df=pd.DataFrame(history).copy()
        for _col in ["orcamento","valor_estimado","valor_real","saldo","quantidade_itens"]:
            if _col not in hist_df.columns: hist_df[_col]=0
            hist_df["_"+_col]=hist_df[_col].apply(num)
        if "id" not in hist_df.columns: hist_df["id"]=range(1,len(hist_df)+1)
        if "data_compra" not in hist_df.columns: hist_df["data_compra"]=""
        hist_df["_id"]=hist_df["id"].astype(str)
        hist_df["_data"]=pd.to_datetime(hist_df["data_compra"],errors="coerce",utc=True).dt.tz_convert(None)

        _period=st.selectbox("Período de análise",["Todo o histórico","Últimos 30 dias","Últimos 90 dias","Ano atual"],key="analysis_period")
        _filtered=hist_df.copy()
        _today=pd.Timestamp.now(tz="UTC").tz_convert(None)
        if _period=="Últimos 30 dias":
            _filtered=_filtered[_filtered["_data"].notna() & (_filtered["_data"]>=_today-pd.Timedelta(days=30))]
        elif _period=="Últimos 90 dias":
            _filtered=_filtered[_filtered["_data"].notna() & (_filtered["_data"]>=_today-pd.Timedelta(days=90))]
        elif _period=="Ano atual":
            _filtered=_filtered[_filtered["_data"].notna() & (_filtered["_data"].dt.year==_today.year)]

        if _filtered.empty:
            st.warning("Não há compras no período selecionado.")
        else:
            _filtered=_filtered.sort_values(["_data","_id"],na_position="last")
            _purchase_ids=set(_filtered["_id"].tolist())
            try:
                _all_items=db("itens_compra",params={"select":"compra_id,produto_id,nome_produto,quantidade,preco_estimado,preco_unitario,valor_total,variacao_preco,criado_em"})
            except Exception:
                _all_items=[]
            _items=pd.DataFrame(_all_items)
            if not _items.empty:
                if "compra_id" not in _items.columns: _items["compra_id"]=""
                _items["_compra_id"]=_items["compra_id"].astype(str)
                _items=_items[_items["_compra_id"].isin(_purchase_ids)].copy()
                for _col in ["quantidade","preco_estimado","preco_unitario","valor_total","variacao_preco"]:
                    if _col not in _items.columns: _items[_col]=0
                    _items["_"+_col]=_items[_col].apply(num)
                _items["_valor_real"]=_items.apply(lambda _r: num(_r.get("valor_total")) if num(_r.get("valor_total")) else num(_r.get("quantidade"))*num(_r.get("preco_unitario")),axis=1)
                _prod_id={str(_p.get("id")):_p for _p in products}
                _prod_name={norm(_p.get("nome")):_p for _p in products}
                def _analysis_category(_r):
                    _p=_prod_id.get(str(_r.get("produto_id"))) or _prod_name.get(norm(_r.get("nome_produto")))
                    return (_p.get("categoria") if _p else None) or "Sem categoria"
                _items["_categoria"]=_items.apply(_analysis_category,axis=1)
                _order_map={str(_r["_id"]):_i for _i,(_, _r) in enumerate(_filtered.iterrows())}
                _items["_ordem"]=_items["_compra_id"].map(_order_map).fillna(-1)

            _n=len(_filtered)
            _real=float(_filtered["_valor_real"].sum())
            _est=float(_filtered["_valor_estimado"].sum())
            _budget=float(_filtered["_orcamento"].sum())
            _ticket=_real/_n if _n else 0
            _saving=_est-_real
            _budget_rows=_filtered[_filtered["_orcamento"]>0]
            _adherence=((_budget_rows["_valor_real"]<=_budget_rows["_orcamento"]).mean() if not _budget_rows.empty else None)
            _avg_items=float(_filtered["_quantidade_itens"].mean()) if _n else 0

            _k1,_k2,_k3,_k4=st.columns(4)
            _k1.metric("Gasto acumulado",money(_real))
            _k2.metric("Ticket médio",money(_ticket))
            _k3.metric("Economia vs estimado",money(_saving),delta=(f"{(_saving/_est*100):+.1f}%" if _est else None))
            _k4.metric("Dentro do orçamento",f"{_adherence:.0%}" if _adherence is not None else "—")
            _s1,_s2,_s3,_s4=st.columns(4)
            _s1.metric("Compras analisadas",_n)
            _s2.metric("Orçamento acumulado",money(_budget))
            _s3.metric("Estimado acumulado",money(_est))
            _s4.metric("Itens médios / compra",f"{_avg_items:.1f}")

            _overview,_evolution,_products_tab,_categories_tab=st.tabs(["Resumo executivo","Evolução","Produtos","Categorias"])

            with _overview:
                st.markdown("#### Leitura executiva")
                _most_expensive=_filtered.loc[_filtered["_valor_real"].idxmax()]
                _best_save_idx=(_filtered["_valor_estimado"]-_filtered["_valor_real"]).idxmax()
                _best_save=_filtered.loc[_best_save_idx]
                _overspend=(_filtered["_valor_real"]-_filtered["_orcamento"]).where(_filtered["_orcamento"]>0,0)
                _worst_idx=_overspend.idxmax()
                _worst_value=float(_overspend.loc[_worst_idx]) if len(_overspend) else 0
                _most_date=_most_expensive["_data"].strftime("%d/%m/%Y") if pd.notna(_most_expensive["_data"]) else "sem data"
                _best_date=_best_save["_data"].strftime("%d/%m/%Y") if pd.notna(_best_save["_data"]) else "sem data"
                _c1,_c2=st.columns(2)
                with _c1:
                    st.markdown(f'<div class="card"><div class="label">MAIOR COMPRA</div><div class="value">{money(_most_expensive["_valor_real"])}</div><div class="muted">{_most_date}</div></div>',unsafe_allow_html=True)
                with _c2:
                    _best_value=num(_best_save.get("_valor_estimado"))-num(_best_save.get("_valor_real"))
                    st.markdown(f'<div class="card"><div class="label">MELHOR ECONOMIA VS ESTIMADO</div><div class="value">{money(_best_value)}</div><div class="muted">{_best_date}</div></div>',unsafe_allow_html=True)
                _c3,_c4=st.columns(2)
                with _c3:
                    if _worst_value>0:
                        _wr=_filtered.loc[_worst_idx]
                        _wd=_wr["_data"].strftime("%d/%m/%Y") if pd.notna(_wr["_data"]) else "sem data"
                        st.markdown(f'<div class="card"><div class="label">MAIOR ESTOURO DE ORÇAMENTO</div><div class="value">{money(_worst_value)}</div><div class="muted">{_wd}</div></div>',unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="card"><div class="label">CONTROLE ORÇAMENTÁRIO</div><div class="value">Sem estouro</div><div class="muted">Nenhuma compra acima do orçamento no período.</div></div>',unsafe_allow_html=True)
                with _c4:
                    if not _items.empty:
                        _impact=_items.groupby("nome_produto",dropna=False)["_valor_real"].sum().sort_values(ascending=False)
                        if len(_impact):
                            _top_name=str(_impact.index[0]); _top_value=float(_impact.iloc[0])
                            st.markdown(f'<div class="card"><div class="label">PRODUTO DE MAIOR IMPACTO</div><div class="value">{_top_name}</div><div class="muted">{money(_top_value)} acumulados</div></div>',unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="card"><div class="label">PRODUTO DE MAIOR IMPACTO</div><div class="value">—</div></div>',unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="card"><div class="label">PRODUTO DE MAIOR IMPACTO</div><div class="value">—</div></div>',unsafe_allow_html=True)

                st.markdown("#### Controle por compra")
                _control=_filtered.sort_values("_data",ascending=False).copy()
                _control_display=pd.DataFrame({
                    "Data":[_d.strftime("%d/%m/%Y") if pd.notna(_d) else "—" for _d in _control["_data"]],
                    "Orçamento":[money(_v) for _v in _control["_orcamento"]],
                    "Estimado":[money(_v) for _v in _control["_valor_estimado"]],
                    "Real":[money(_v) for _v in _control["_valor_real"]],
                    "Economia vs estimado":[money(_e-_r) for _e,_r in zip(_control["_valor_estimado"],_control["_valor_real"])],
                    "Uso do orçamento":[f"{(_r/_b*100):.1f}%" if _b>0 else "—" for _r,_b in zip(_control["_valor_real"],_control["_orcamento"])],
                    "Status":["Dentro" if (_b<=0 or _r<=_b) else "Acima" for _r,_b in zip(_control["_valor_real"],_control["_orcamento"])]
                })
                st.dataframe(_control_display,use_container_width=True,hide_index=True)

            with _evolution:
                st.markdown("#### Evolução das compras")
                _evo=_filtered.sort_values("_data").copy().reset_index(drop=True)
                _evo["Compra"]=[f"{_i+1} · "+(_d.strftime("%d/%m/%Y") if pd.notna(_d) else "sem data") for _i,_d in enumerate(_evo["_data"])]
                _evo_chart=pd.DataFrame({"Compra":_evo["Compra"],"Orçamento":_evo["_orcamento"],"Estimado":_evo["_valor_estimado"],"Real":_evo["_valor_real"]}).set_index("Compra")
                st.line_chart(_evo_chart,use_container_width=True)
                _dated=_filtered[_filtered["_data"].notna()].copy()
                if not _dated.empty:
                    _dated["Mês"]=_dated["_data"].dt.to_period("M").astype(str)
                    _monthly=_dated.groupby("Mês")["_valor_real"].sum().to_frame("Gasto")
                    st.markdown("#### Gasto por mês")
                    st.bar_chart(_monthly,use_container_width=True)
                _desvio=pd.DataFrame({
                    "Compra":_evo["Compra"],
                    "Desvio vs estimado":[money(_r-_e) for _r,_e in zip(_evo["_valor_real"],_evo["_valor_estimado"])],
                    "Desvio %":[f"{((_r-_e)/_e*100):+.1f}%" if _e else "—" for _r,_e in zip(_evo["_valor_real"],_evo["_valor_estimado"])]
                })
                st.dataframe(_desvio,use_container_width=True,hide_index=True)

            with _products_tab:
                if _items.empty:
                    st.info("Não há itens suficientes no histórico para analisar produtos.")
                else:
                    st.markdown("#### Produtos de maior impacto financeiro")
                    _pg=_items.groupby("nome_produto",dropna=False).agg(Gasto=("_valor_real","sum"),Quantidade=("_quantidade","sum"),Compras=("_compra_id","nunique")).reset_index().rename(columns={"nome_produto":"Produto"})
                    _pg=_pg.sort_values("Gasto",ascending=False)
                    _top=_pg.head(10)
                    if not _top.empty:
                        st.bar_chart(_top.set_index("Produto")[["Gasto"]],use_container_width=True)
                        _top_display=_top.copy(); _top_display["Gasto"]=_top_display["Gasto"].apply(money); _top_display["Quantidade"]=_top_display["Quantidade"].map(lambda _x:f"{_x:g}")
                        st.dataframe(_top_display,use_container_width=True,hide_index=True)

                    st.markdown("#### Recorrência de compra")
                    _freq=_pg.sort_values(["Compras","Gasto"],ascending=[False,False]).head(10).copy()
                    _freq["Gasto"]=_freq["Gasto"].apply(money); _freq["Quantidade"]=_freq["Quantidade"].map(lambda _x:f"{_x:g}")
                    st.dataframe(_freq,use_container_width=True,hide_index=True)

                    _variations=[]
                    _priced=_items[_items["_preco_unitario"]>0].copy()
                    for _name,_grp in _priced.groupby("nome_produto",dropna=False):
                        _grp=_grp.sort_values(["_ordem","criado_em"] if "criado_em" in _grp.columns else ["_ordem"])
                        _prices=[float(_x) for _x in _grp["_preco_unitario"].tolist() if float(_x)>0]
                        if len(_prices)>=2 and _prices[-2]>0:
                            _prev,_last=_prices[-2],_prices[-1]
                            _pct=(_last-_prev)/_prev*100
                            _variations.append({"Produto":str(_name),"Anterior":_prev,"Atual":_last,"Variação %":_pct})
                    if _variations:
                        _var_df=pd.DataFrame(_variations)
                        _var_df["_abs"]=_var_df["Variação %"].abs(); _var_df=_var_df.sort_values("_abs",ascending=False).head(10).drop(columns=["_abs"])
                        _var_display=_var_df.copy(); _var_display["Anterior"]=_var_display["Anterior"].apply(money); _var_display["Atual"]=_var_display["Atual"].apply(money); _var_display["Variação %"]=_var_display["Variação %"].map(lambda _x:f"{_x:+.1f}%")
                        st.markdown("#### Maiores variações recentes de preço")
                        st.dataframe(_var_display,use_container_width=True,hide_index=True)

            with _categories_tab:
                if _items.empty:
                    st.info("Não há itens suficientes no histórico para analisar categorias.")
                else:
                    st.markdown("#### Participação por categoria")
                    _cat=_items.groupby("_categoria")["_valor_real"].sum().sort_values(ascending=False)
                    _cat_df=_cat.to_frame("Gasto")
                    st.bar_chart(_cat_df,use_container_width=True)
                    _cat_total=float(_cat.sum())
                    _cat_table=_cat.reset_index().rename(columns={"_categoria":"Categoria","_valor_real":"Gasto"})
                    _cat_table["Participação"]=_cat_table["Gasto"].map(lambda _x:f"{(_x/_cat_total*100):.1f}%" if _cat_total else "0.0%")
                    _cat_table["Gasto"]=_cat_table["Gasto"].apply(money)
                    st.dataframe(_cat_table,use_container_width=True,hide_index=True)
'''

# Este bloco precisa ser executado dentro do wrapper 0074, porque é nele
# que _source já contém o texto final de app_original.py.
inner = (
    "\nimport re as _patch_re\n"
    "if 'def move_item_to_next_list' not in _source:\n"
    "    _source = _source.replace('def add_item(', " + repr(next_helpers + "def add_item(") + ", 1)\n"
    "_patch_pattern = r'def add_item\\(name,cat,unit,qty,price\\):.*?\\ndef edit_item'\n"
    "_source, _patch_count = _patch_re.subn(_patch_pattern, " + repr(safe_add + "\ndef edit_item") + ", _source, count=1, flags=_patch_re.S)\n"
    "if _patch_count != 1:\n"
    "    raise RuntimeError('Tratamento de item duplicado nao foi aplicado.')\n"
    "_analysis_pattern = r'with ana:.*?(?=\\nwith config:)'\n"
    "_source = _patch_re.sub(_analysis_pattern, " + repr(professional_analysis) + ", _source, count=1, flags=_patch_re.S)\n"
)

# A fonte carregada aqui é o wrapper 687. Antes de ele executar o 0074,
# inserimos no texto do 0074 o patch acima. O marcador abaixo é o final
# real do 0074, não o final do 687.
inner_marker = 'exec(compile(_source,"app_original.py","exec"),globals(),globals())'
outer_marker = 'exec(compile(_source, str(Path(__file__)), "exec"))'
bridge = (
    "\n_inner_marker = " + repr(inner_marker) + "\n"
    "_inner_patch = " + repr(inner) + "\n"
    "if _inner_marker not in _source:\n"
    "    raise RuntimeError('Ponto de execucao do app_original nao encontrado no 0074.')\n"
    "_source = _source.replace(_inner_marker, _inner_patch + _inner_marker, 1)\n"
)

pos = source.rfind(outer_marker)
if pos < 0:
    raise RuntimeError("Execucao do 687 nao encontrada.")
source = source[:pos] + bridge + source[pos:]

if "hist" not in globals():
    hist = st.container()

exec(compile(source, str(Path(__file__)), "exec"))