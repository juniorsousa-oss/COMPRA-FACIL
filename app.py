from pathlib import Path
import urllib.request

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/7f2b1a03b75113c6d810a29cff3d4593c818c46f/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

# A infraestrutura de preço sugerido fica no banco. Aqui acrescentamos apenas
# a gestão visual desses valores na aba Produtos, sem alterar os fluxos já validados.
_original_read_text = Path.read_text

_old_products_block = '''with prod:
    st.subheader("Produtos")
    if st.button("Adicionar novo produto",type="primary",use_container_width=True,key="open_new_product"): new_product_dialog(products)
    if st.button("Atualizar informações dos produtos pelo histórico",use_container_width=True,key="rebuild_product_stats"):
        try: st.success(f"Informações atualizadas para {rebuild_product_stats(products)} produtos."); st.rerun()
        except Exception as e: st.error(f"Erro: {e}")
    with st.expander("Importar lista Excel",expanded=False):
        up=st.file_uploader("Escolher arquivo Excel",type=["xlsx","xlsm"],key="excel_products")
        if up is not None:
            try:
                imp,skip=import_products_excel(up,products); st.success(f"{len(imp)} produtos novos; {skip} linhas ignoradas.")
                if imp and st.button("Cadastrar apenas os novos produtos",type="primary",use_container_width=True,key="import_confirm"): db("produtos","POST",data=imp); clear(); st.rerun()
            except Exception as e: st.error(f"Erro na importação: {e}")
    search=st.text_input("Pesquisar produto",placeholder="Arroz, leite, sabão..."); rows=[p for p in products if not search.strip() or search.lower() in p.get("nome","").lower()]
    if rows: st.dataframe(pd.DataFrame([{"Produto":p.get("nome"),"Categoria":p.get("categoria"),"Unidade":p.get("unidade"),"Último":money(p.get("ultimo_preco")),"Médio":money(p.get("preco_medio")),"Menor":money(p.get("menor_preco")),"Maior":money(p.get("maior_preco")),"Compras":p.get("quantidade_compras",0)} for p in rows]),use_container_width=True,hide_index=True)
'''

_new_products_block = '''with prod:
    st.subheader("Produtos")
    if st.button("Adicionar novo produto",type="primary",use_container_width=True,key="open_new_product"): new_product_dialog(products)
    if st.button("Atualizar informações dos produtos pelo histórico",use_container_width=True,key="rebuild_product_stats"):
        try: st.success(f"Informações atualizadas para {rebuild_product_stats(products)} produtos."); st.rerun()
        except Exception as e: st.error(f"Erro: {e}")

    with st.expander("Preço sugerido para produtos sem histórico",expanded=False):
        st.caption("Regra usada nas novas listas: primeiro o último preço real; se não existir, o preço sugerido; se ambos estiverem vazios, o produto permanece sem referência.")
        _suggest_names=[p.get("nome","") for p in products if p.get("nome")]
        if _suggest_names:
            _suggest_name=st.selectbox("Produto",_suggest_names,key="suggested_price_product")
            _suggest_product=find_product(products,_suggest_name)
            _s1,_s2=st.columns([1,2])
            with _s1:
                _suggest_value=st.number_input("Preço sugerido (R$)",min_value=0.0,value=num(_suggest_product.get("preco_sugerido")) if _suggest_product else 0.0,step=.01,format="%.2f",key=f"suggested_price_value_{_suggest_product.get('id') if _suggest_product else 0}")
            with _s2:
                _suggest_source=st.text_input("Fonte / referência",value=str((_suggest_product or {}).get("fonte_preco_sugerido") or ""),placeholder="Ex.: média regional semanal",key=f"suggested_price_source_{_suggest_product.get('id') if _suggest_product else 0}")
            if st.button("Salvar preço sugerido",type="primary",use_container_width=True,key="save_suggested_price") and _suggest_product:
                db("produtos","PATCH",params={"id":f"eq.{_suggest_product['id']}"},data={"preco_sugerido":num(_suggest_value),"fonte_preco_sugerido":_suggest_source.strip() or None,"preco_sugerido_atualizado_em":now()})
                clear(); st.rerun()

        st.divider()
        st.markdown("**Atualização em lote pelo relatório semanal**")
        st.caption("O Excel deve ter as colunas PRODUTO e PREÇO SUGERIDO. A coluna FONTE é opcional.")
        _suggest_file=st.file_uploader("Importar relatório de preços sugeridos",type=["xlsx","xlsm"],key="suggested_price_excel")
        if _suggest_file is not None:
            try:
                _sdf=pd.read_excel(_suggest_file,dtype=object)
                _cols={norm(c):c for c in _sdf.columns}
                _cp=next((_cols.get(norm(x)) for x in ["PRODUTO","NOME"] if _cols.get(norm(x))),None)
                _cv=next((_cols.get(norm(x)) for x in ["PREÇO SUGERIDO","PRECO SUGERIDO","PREÇO","PRECO","VALOR"] if _cols.get(norm(x))),None)
                _cf=next((_cols.get(norm(x)) for x in ["FONTE","REFERÊNCIA","REFERENCIA"] if _cols.get(norm(x))),None)
                if not _cp or not _cv:
                    st.error("O relatório precisa conter PRODUTO e PREÇO SUGERIDO.")
                else:
                    _by_name={norm(p.get("nome")):p for p in products}
                    _preview=[]; _updates=[]; _skipped=0
                    for _,_r in _sdf.iterrows():
                        _name=str(_r.get(_cp,"") or "").strip(); _value=num(_r.get(_cv)); _p=_by_name.get(norm(_name))
                        if not _name or _value<=0 or not _p:
                            _skipped+=1; continue
                        _source_value=str(_r.get(_cf,"") or "").strip() if _cf else ""
                        _updates.append((_p,_value,_source_value))
                        _preview.append({"Produto":_p.get("nome"),"Preço sugerido":money(_value),"Fonte":_source_value or "—","Base atual":"Último preço" if num(_p.get("ultimo_preco"))>0 else "Sugerido"})
                    if _preview:
                        st.dataframe(pd.DataFrame(_preview),use_container_width=True,hide_index=True)
                        st.caption(f"{len(_updates)} produto(s) serão atualizados; {_skipped} linha(s) foram ignoradas.")
                        if st.button("Aplicar preços sugeridos",type="primary",use_container_width=True,key="apply_suggested_prices"):
                            for _p,_value,_source_value in _updates:
                                db("produtos","PATCH",params={"id":f"eq.{_p['id']}"},data={"preco_sugerido":num(_value),"fonte_preco_sugerido":_source_value or None,"preco_sugerido_atualizado_em":now()})
                            clear(); st.success(f"{len(_updates)} preço(s) sugerido(s) atualizado(s)."); st.rerun()
                    else:
                        st.warning("Nenhum produto cadastrado com preço válido foi encontrado no relatório.")
            except Exception as e:
                st.error(f"Erro ao ler o relatório de preços sugeridos: {e}")

    with st.expander("Importar lista Excel",expanded=False):
        up=st.file_uploader("Escolher arquivo Excel",type=["xlsx","xlsm"],key="excel_products")
        if up is not None:
            try:
                imp,skip=import_products_excel(up,products); st.success(f"{len(imp)} produtos novos; {skip} linhas ignoradas.")
                if imp and st.button("Cadastrar apenas os novos produtos",type="primary",use_container_width=True,key="import_confirm"): db("produtos","POST",data=imp); clear(); st.rerun()
            except Exception as e: st.error(f"Erro na importação: {e}")
    search=st.text_input("Pesquisar produto",placeholder="Arroz, leite, sabão..."); rows=[p for p in products if not search.strip() or search.lower() in p.get("nome","").lower()]
    if rows:
        _product_rows=[]
        for p in rows:
            _last=num(p.get("ultimo_preco")); _suggest=num(p.get("preco_sugerido")); _base=_last if _last>0 else _suggest
            _origin="Último preço" if _last>0 else ("Sugerido" if _suggest>0 else "Sem referência")
            _product_rows.append({"Produto":p.get("nome"),"Categoria":p.get("categoria"),"Unidade":p.get("unidade"),"Último":money(_last),"Sugerido":money(_suggest),"Base nova lista":money(_base),"Origem":_origin,"Médio":money(p.get("preco_medio")),"Menor":money(p.get("menor_preco")),"Maior":money(p.get("maior_preco")),"Compras":p.get("quantidade_compras",0),"Fonte sugerida":p.get("fonte_preco_sugerido") or "—","Atualizado":str(p.get("preco_sugerido_atualizado_em") or "")[:10] or "—"})
        st.dataframe(pd.DataFrame(_product_rows),use_container_width=True,hide_index=True)
'''

def _patched_read_text(self, *args, **kwargs):
    text = _original_read_text(self, *args, **kwargs)
    if self.name == "app_original.py":
        if _old_products_block not in text:
            raise RuntimeError("Bloco de Produtos para preço sugerido não encontrado.")
        text = text.replace(_old_products_block, _new_products_block, 1)
    return text

Path.read_text = _patched_read_text

exec(compile(source, str(Path(__file__)), "exec"))
