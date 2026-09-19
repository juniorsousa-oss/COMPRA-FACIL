from pathlib import Path
import urllib.request
import streamlit as st

# Mantém toda a versão já validada do app e acrescenta apenas a identificação
# do supermercado no momento da finalização da compra.
BASE = "https://raw.githubusercontent.com/juniorsousa-oss/COMPRA-FACIL/1e4ada77cce7266f607ef7712c2714046ddecf6d/app.py"
source = urllib.request.urlopen(BASE, timeout=10).read().decode("utf-8")

_original_button = st.button

def _button_with_market(label, *args, **kwargs):
    clicked = _original_button(label, *args, **kwargs)
    if label == "Finalizar e salvar compra" and clicked:
        st.session_state["finish_market_requested"] = True
        return False
    return clicked

# Impede que o fluxo antigo finalize imediatamente. Ao clicar em finalizar,
# abrimos primeiro a identificação do supermercado.
st.button = _button_with_market
try:
    exec(compile(source, str(Path(__file__)), "exec"), globals(), globals())
finally:
    st.button = _original_button


def _finish_with_market(items, purchase_budget, market):
    """Executa a finalização já existente e injeta o supermercado no registro."""
    _original_db = globals()["db"]

    def _db_with_market(table, method="GET", params=None, data=None):
        if table == "compras" and method == "POST" and isinstance(data, dict):
            data = dict(data)
            data["supermercado"] = market.strip()
        return _original_db(table, method, params, data)

    globals()["db"] = _db_with_market
    try:
        return globals()["finish"](items, purchase_budget)
    finally:
        globals()["db"] = _original_db


@st.dialog("Finalizar compra")
def _market_dialog():
    st.markdown("### Onde esta compra foi realizada?")
    st.caption("O supermercado ficará vinculado ao histórico desta compra para permitir comparações futuras de preços e gastos por estabelecimento.")

    _known_markets = sorted({
        str(p.get("supermercado") or "").strip()
        for p in globals().get("history", [])
        if str(p.get("supermercado") or "").strip()
    }, key=str.lower)

    _market = ""
    if _known_markets:
        _choice = st.selectbox(
            "Supermercado",
            ["Selecione..."] + _known_markets + ["Outro supermercado"],
            key="finish_market_choice",
        )
        if _choice == "Outro supermercado":
            _market = st.text_input(
                "Nome do supermercado",
                placeholder="Ex.: Supermercado X",
                key="finish_market_other",
            ).strip()
        elif _choice != "Selecione...":
            _market = _choice
    else:
        _market = st.text_input(
            "Supermercado",
            placeholder="Ex.: Supermercado X",
            key="finish_market_first",
        ).strip()

    _a, _b = st.columns(2)
    if _a.button("Cancelar", use_container_width=True, key="cancel_finish_market"):
        st.session_state.pop("finish_market_requested", None)
        st.rerun()

    if _b.button("Finalizar compra", type="primary", use_container_width=True, key="confirm_finish_market"):
        if not _market:
            st.error("Informe o supermercado onde a compra foi realizada.")
        else:
            try:
                _finish_with_market(globals().get("current", []), globals().get("budget", 0), _market)
                st.session_state.pop("finish_market_requested", None)
                st.session_state.pop("finish_market_choice", None)
                st.session_state.pop("finish_market_other", None)
                st.session_state.pop("finish_market_first", None)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao finalizar: {e}")


def _ocr_extract_text(file_bytes):
    """Lê texto de foto/print localmente no servidor usando Tesseract."""
    import io as _io
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    import pytesseract

    image = Image.open(_io.BytesIO(file_bytes)).convert("RGB")
    width, height = image.size
    if max(width, height) < 1800:
        scale = min(2.2, 1800 / max(width, height))
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(1.5)
    image = image.filter(ImageFilter.SHARPEN)

    config = "--oem 3 --psm 6"
    try:
        return pytesseract.image_to_string(image, lang="por+eng", config=config)
    except Exception:
        return pytesseract.image_to_string(image, lang="eng", config=config)


def _ocr_parse_line(line):
    """Extrai nome provável do produto e quantidade de uma linha reconhecida."""
    import re as _re

    raw = _re.sub(r"\s+", " ", str(line or "")).strip()
    if not raw:
        return None
    s = _re.sub(r"^[\s\-–—•·*✓✔☐☑\[\]()]+", "", raw).strip()
    s = _re.sub(r"^\d{1,2}[\.)\-:]\s*", "", s).strip()
    s = _re.sub(r"\s+R\$\s*\d+[\.,]\d{1,2}\s*$", "", s, flags=_re.I).strip()
    s = _re.sub(r"\s+\d+[\.,]\d{2}\s*$", "", s).strip()

    lowered = s.casefold()
    if lowered in {"lista", "lista de compras", "compras", "mercado", "supermercado", "produto", "produtos"}:
        return None
    if len(s) < 2:
        return None

    qty = 1.0
    m = _re.match(r"^(\d+(?:[\.,]\d+)?)\s*[xX]\s+(.+)$", s)
    if m:
        qty = float(m.group(1).replace(",", "."))
        s = m.group(2).strip()
    else:
        m = _re.match(r"^(\d+(?:[\.,]\d+)?)\s+(?:un\.?|und\.?|unid\.?|unidades?)\s+(.+)$", s, flags=_re.I)
        if m:
            qty = float(m.group(1).replace(",", "."))
            s = m.group(2).strip()
        else:
            m = _re.match(r"^(.+?)\s+[xX]\s*(\d+(?:[\.,]\d+)?)$", s)
            if m:
                s = m.group(1).strip()
                qty = float(m.group(2).replace(",", "."))

    s = _re.sub(r"\s+", " ", s).strip(" -–—:;,.|")
    if len(s) < 2:
        return None
    return {"raw": raw, "name": s, "qty": max(qty, 0.001)}


def _ocr_build_candidates(text, products):
    """Monta candidatos e sugere o melhor produto já cadastrado."""
    candidates = []
    seen = set()
    _find = globals()["find_product"]
    _suggestions = globals()["suggestions"]
    _norm = globals()["norm"]

    for line in str(text or "").splitlines():
        parsed = _ocr_parse_line(line)
        if not parsed:
            continue
        key = _norm(parsed["name"])
        if not key or key in seen:
            continue
        seen.add(key)
        exact = _find(products, parsed["name"])
        best = exact
        score = 1.0 if exact else 0.0
        if not best:
            sims = _suggestions(parsed["name"], products, limit=3)
            if sims:
                score, best = sims[0]
        candidates.append({**parsed, "suggested": best.get("nome") if best else None, "score": score})
        if len(candidates) >= 40:
            break
    return candidates


def _clear_ocr_state():
    for key in (
        "photo_import_requested", "photo_ocr_text", "photo_ocr_candidates",
        "photo_import_file"
    ):
        st.session_state.pop(key, None)


@st.dialog("Adicionar itens por foto ou print", width="large")
def _photo_import_dialog():
    products = globals().get("products", [])
    current = globals().get("current", [])
    _norm = globals()["norm"]
    _num = globals()["num"]

    st.caption("Envie uma foto ou print de uma lista. O app lê o texto e deixa você revisar os itens antes de incluí-los.")
    uploaded = st.file_uploader(
        "Foto ou print da lista",
        type=["png", "jpg", "jpeg", "webp"],
        key="photo_import_file",
    )

    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True, key="photo_cancel"):
        _clear_ocr_state()
        st.rerun()

    if c2.button("Ler imagem", type="primary", use_container_width=True, key="photo_read"):
        if uploaded is None:
            st.warning("Selecione uma imagem primeiro.")
        else:
            try:
                with st.spinner("Lendo a imagem..."):
                    text = _ocr_extract_text(uploaded.getvalue())
                    candidates = _ocr_build_candidates(text, products)
                st.session_state["photo_ocr_text"] = text
                st.session_state["photo_ocr_candidates"] = candidates
            except Exception as e:
                st.error(f"Não consegui ler essa imagem: {e}")

    text = st.session_state.get("photo_ocr_text", "")
    candidates = st.session_state.get("photo_ocr_candidates") or []

    if text:
        with st.expander("Texto reconhecido", expanded=False):
            st.text(text[:6000])

    if candidates:
        st.markdown("#### Revisar itens encontrados")
        st.caption("A correspondência é apenas uma sugestão. Confirme o produto e a quantidade antes de adicionar.")
        names = [p.get("nome", "") for p in products if p.get("nome")]
        options = ["— Ignorar —", "— Selecionar produto —"] + names
        selected_rows = []

        for i, candidate in enumerate(candidates):
            st.markdown(f"**Reconhecido:** {candidate['raw']}")
            default_name = candidate.get("suggested")
            default_index = options.index(default_name) if default_name in options else 1
            a, b = st.columns([3, 1])
            choice = a.selectbox(
                "Produto cadastrado",
                options,
                index=default_index,
                key=f"ocr_product_{i}",
                label_visibility="collapsed",
            )
            qty = b.number_input(
                "Qtd",
                min_value=0.001,
                value=float(candidate.get("qty") or 1),
                step=1.0,
                format="%.2f",
                key=f"ocr_qty_{i}",
            )
            if choice not in ("— Ignorar —", "— Selecionar produto —"):
                selected_rows.append((choice, qty))
            st.divider()

        if st.button("Adicionar itens selecionados", type="primary", use_container_width=True, key="ocr_add_selected"):
            if not selected_rows:
                st.warning("Selecione pelo menos um produto.")
            else:
                try:
                    current_keys = {_norm(x.get("nome_produto")) for x in current}
                    added = 0
                    skipped = []
                    by_name = {_norm(p.get("nome")): p for p in products}
                    for name, qty in selected_rows:
                        key = _norm(name)
                        if key in current_keys:
                            skipped.append(name)
                            continue
                        p = by_name.get(key)
                        if not p:
                            skipped.append(name)
                            continue
                        price = _num(p.get("ultimo_preco")) or _num(p.get("preco_sugerido"))
                        globals()["add_item"](
                            p.get("nome"),
                            p.get("categoria", "Mercearia"),
                            p.get("unidade", "un."),
                            qty,
                            price,
                        )
                        current_keys.add(key)
                        added += 1
                    _clear_ocr_state()
                    if skipped:
                        st.session_state["photo_import_result"] = f"{added} item(ns) adicionado(s). {len(skipped)} ignorado(s) por já estarem na lista ou não serem válidos."
                    else:
                        st.session_state["photo_import_result"] = f"{added} item(ns) adicionado(s) pela imagem."
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao incluir os itens: {e}")
    elif text:
        st.warning("Não encontrei linhas de produtos com segurança. Tente uma imagem mais nítida ou com a lista ocupando mais espaço.")


# A funcionalidade fica dentro da aba Compra sem interferir nos fluxos já validados.
if "buy" in globals():
    with globals()["buy"]:
        st.divider()
        st.markdown("### Adicionar por foto ou print")
        st.caption("Fotografe uma lista ou envie um print. Você revisa o reconhecimento antes de incluir os itens.")
        if st.button("Ler foto ou print da lista", use_container_width=True, key="open_photo_import"):
            st.session_state["photo_import_requested"] = True
            st.rerun()
        if st.session_state.get("photo_import_result"):
            st.success(st.session_state.pop("photo_import_result"))


if st.session_state.get("finish_market_requested"):
    _market_dialog()

if st.session_state.get("photo_import_requested"):
    _photo_import_dialog()
