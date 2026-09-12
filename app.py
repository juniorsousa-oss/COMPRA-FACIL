from pathlib import Path
import urllib.request

BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/6fdf49f65e247f0d256f4929008bcf937b78c705/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

# Ao selecionar o produto alternativo na confirmação, usa a referência
# de preço do próprio alternativo quando houver histórico. A lista continua
# sendo planejada pelo produto principal até a escolha no momento da compra.
_old_confirm = '''    reference=estimated
    if alt and norm(choice)==norm(alt): reference=num(item.get("preco_estimado_alternativo")) or estimated
    price=st.number_input("Preço unitário pago",min_value=0.,value=num(item.get("preco_unitario")) or reference,step=.01,format="%.2f",key=f"confirm_price_{item['id']}_{norm(choice)}")
    variation=price-estimated; variation_pct=(variation/estimated*100) if estimated else None
    c1,c2=st.columns(2)
    with c1: st.metric("Base estimada",money(estimated))
    with c2: st.metric("Variação",money(variation),delta=f"{variation_pct:+.1f}%" if variation_pct is not None else None)
    if alt and norm(choice)==norm(alt): st.info(f"Será registrado como compra de {alt}, mantendo {main} como produto planejado.")
    if estimated:
        if variation > 0: st.warning(f"Preço {money(variation)} acima da base estimada ({variation_pct:+.1f}%).")
        elif variation < 0: st.success(f"Economia de {money(abs(variation))} ({abs(variation_pct):.1f}%) em relação à base estimada.")
        else: st.info("Preço igual ao valor estimado.")
'''

_new_confirm = '''    reference=estimated
    reference_name=main
    used_alt_reference=False
    if alt and norm(choice)==norm(alt):
        alt_saved=num(item.get("preco_estimado_alternativo"))
        alt_product=find_product(get_products(),alt)
        alt_live=num(alt_product.get("ultimo_preco")) if alt_product else 0
        alt_reference=alt_live or alt_saved
        if alt_reference>0:
            reference=alt_reference
            reference_name=alt
            used_alt_reference=True
        else:
            reference=estimated
            reference_name=main
    price=st.number_input("Preço unitário pago",min_value=0.,value=num(item.get("preco_unitario")) or reference,step=.01,format="%.2f",key=f"confirm_price_{item['id']}_{norm(choice)}")
    variation=price-reference; variation_pct=(variation/reference*100) if reference else None
    c1,c2=st.columns(2)
    with c1: st.metric(f"Base estimada · {reference_name}",money(reference))
    with c2: st.metric("Variação",money(variation),delta=f"{variation_pct:+.1f}%" if variation_pct is not None else None)
    if alt and norm(choice)==norm(alt):
        if used_alt_reference:
            st.info(f"Será registrado como compra de {alt}. A comparação de preço usa a última referência de {alt}; {main} continua como produto originalmente planejado.")
        else:
            st.info(f"{alt} ainda não possui preço histórico. Será registrado como alternativa, mas a referência de {main} será mantida nesta compra.")
    if reference:
        if variation > 0: st.warning(f"Preço {money(variation)} acima da base estimada ({variation_pct:+.1f}%).")
        elif variation < 0: st.success(f"Economia de {money(abs(variation))} ({abs(variation_pct):.1f}%) em relação à base estimada.")
        else: st.info("Preço igual ao valor estimado.")
'''

if _old_confirm not in source:
    raise RuntimeError("Bloco de referência de preço da alternativa não encontrado.")
source = source.replace(_old_confirm, _new_confirm, 1)

# No histórico do item, grava a referência do produto efetivamente escolhido.
# O total estimado geral da compra continua representando o planejamento original.
_old_finish = '''        q=num(x.get("quantidade")); e=num(x.get("preco_estimado")); p=num(x.get("preco_unitario"))
        planned=x.get("nome_produto"); alt=x.get("produto_alternativo"); chosen=x.get("produto_escolhido") or planned
        is_alt=bool(alt and norm(chosen)==norm(alt))
        chosen_cat=x.get("categoria_alternativa","Mercearia") if is_alt else x.get("categoria","Mercearia")
        chosen_unit=x.get("unidade_alternativa","un.") if is_alt else x.get("unidade","un.")
        pid=create_product(chosen,chosen_cat,chosen_unit,p or e,q)
        rows.append({"compra_id":c["id"],"produto_id":pid,"nome_produto":chosen,"quantidade":q,"unidade":chosen_unit,"preco_estimado":e,"preco_unitario":p,"valor_total":q*p,"ultimo_preco":e,"variacao_preco":p-e,"confirmado":True,"produto_planejado":planned,"produto_alternativo":alt,"foi_alternativa":is_alt})
'''

_new_finish = '''        q=num(x.get("quantidade")); planned_est=num(x.get("preco_estimado")); p=num(x.get("preco_unitario"))
        planned=x.get("nome_produto"); alt=x.get("produto_alternativo"); chosen=x.get("produto_escolhido") or planned
        is_alt=bool(alt and norm(chosen)==norm(alt))
        alt_est=num(x.get("preco_estimado_alternativo"))
        if is_alt:
            alt_product=find_product(get_products(),alt)
            alt_live=num(alt_product.get("ultimo_preco")) if alt_product else 0
            chosen_est=alt_live or alt_est or planned_est
        else:
            chosen_est=planned_est
        chosen_cat=x.get("categoria_alternativa","Mercearia") if is_alt else x.get("categoria","Mercearia")
        chosen_unit=x.get("unidade_alternativa","un.") if is_alt else x.get("unidade","un.")
        pid=create_product(chosen,chosen_cat,chosen_unit,p or chosen_est,q)
        rows.append({"compra_id":c["id"],"produto_id":pid,"nome_produto":chosen,"quantidade":q,"unidade":chosen_unit,"preco_estimado":chosen_est,"preco_unitario":p,"valor_total":q*p,"ultimo_preco":chosen_est,"variacao_preco":p-chosen_est,"confirmado":True,"produto_planejado":planned,"produto_alternativo":alt,"foi_alternativa":is_alt})
'''

if _old_finish not in source:
    raise RuntimeError("Bloco de finalização da alternativa não encontrado.")
source = source.replace(_old_finish, _new_finish, 1)

exec(compile(source, str(Path(__file__)), "exec"))
