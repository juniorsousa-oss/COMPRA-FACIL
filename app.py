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


def _photo_ai_key():
    import os as _os
    try:
        return str(st.secrets.get("GEMINI_API_KEY", _os.getenv("GEMINI_API_KEY", "")) or "").strip()
    except Exception:
        return str(_os.getenv("GEMINI_API_KEY", "") or "").strip()


def _photo_ai_model():
    import os as _os
    try:
        return str(st.secrets.get("GEMINI_VISION_MODEL", _os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash-lite")) or "gemini-2.5-flash-lite").strip()
    except Exception:
        return str(_os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash-lite") or "gemini-2.5-flash-lite").strip()


def _photo_preprocess(file_bytes, for_ai=False):
    """Corrige orientação e melhora a legibilidade sem persistir a imagem."""
    import io as _io
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    image = Image.open(_io.BytesIO(file_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    target = 1800 if not for_ai else 2000
    if max(width, height) < target and not for_ai:
        scale = min(2.2, target / max(width, height))
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))
    elif max(width, height) > target:
        scale = target / max(width, height)
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))

    if for_ai:
        out = _io.BytesIO()
        image.save(out, format="JPEG", quality=88, optimize=True)
        return out.getvalue(), "image/jpeg"

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.55)
    return gray.filter(ImageFilter.SHARPEN)


def _ocr_extract_local(file_bytes):
    """OCR gratuito/local. Retorna texto e confiança média dos termos reconhecidos."""
    import pytesseract
    from pytesseract import Output

    image = _photo_preprocess(file_bytes, for_ai=False)
    config = "--oem 3 --psm 6"
    lang = "por+eng"
    try:
        text = pytesseract.image_to_string(image, lang=lang, config=config)
        data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=Output.DICT)
    except Exception:
        lang = "eng"
        text = pytesseract.image_to_string(image, lang=lang, config=config)
        data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=Output.DICT)

    confs = []
    for raw_conf, raw_text in zip(data.get("conf", []), data.get("text", [])):
        try:
            c = float(raw_conf)
        except Exception:
            continue
        if c >= 0 and str(raw_text or "").strip():
            confs.append(c)
    confidence = sum(confs) / len(confs) if confs else 0.0
    return {"text": text or "", "confidence": confidence}


def _ocr_parse_line(line):
    """Extrai nome provável, quantidade e unidade de uma linha do OCR local."""
    import re as _re

    raw = _re.sub(r"\s+", " ", str(line or "")).strip()
    if not raw:
        return None
    s = _re.sub(r"^[\s\-–—•·*✓✔☐☑\[\]()]+", "", raw).strip()
    s = _re.sub(r"^\d{1,2}[\.)\-:]\s*", "", s).strip()
    s = _re.sub(r"\s+R\$\s*\d+[\.,]\d{1,2}\s*$", "", s, flags=_re.I).strip()
    s = _re.sub(r"\s+\d+[\.,]\d{2}\s*$", "", s).strip()

    lowered = s.casefold()
    if lowered in {"lista", "lista de compras", "compras", "mercado", "supermercado", "produto", "produtos", "no", "date"}:
        return None
    if len(s) < 2:
        return None

    qty = 1.0
    unit = ""
    m = _re.match(r"^(\d+(?:[\.,]\d+)?)\s*(kg|g|ml|l)\b\s*(.+)$", s, flags=_re.I)
    if m:
        qty = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        s = m.group(3).strip()
    else:
        m = _re.match(r"^(\d+(?:[\.,]\d+)?)\s*[xX]\s+(.+)$", s)
        if m:
            qty = float(m.group(1).replace(",", "."))
            s = m.group(2).strip()
        else:
            m = _re.match(r"^(\d+(?:[\.,]\d+)?)\s+(?:un\.?|und\.?|unid\.?|unidades?)\s+(.+)$", s, flags=_re.I)
            if m:
                qty = float(m.group(1).replace(",", "."))
                unit = "un"
                s = m.group(2).strip()
            else:
                m = _re.match(r"^(.+?)\s+[xX]\s*(\d+(?:[\.,]\d+)?)$", s)
                if m:
                    s = m.group(1).strip()
                    qty = float(m.group(2).replace(",", "."))

    alt_name = None
    parts = _re.split(r"\s+ou\s+", s, maxsplit=1, flags=_re.I)
    if len(parts) == 2 and all(x.strip() for x in parts):
        s = parts[0].strip()
        alt_name = parts[1].strip()

    s = _re.sub(r"\s+", " ", s).strip(" -–—:;,.|")
    if len(s) < 2:
        return None
    return {
        "raw": raw,
        "name": s,
        "alt_name": alt_name,
        "qty": max(qty, 0.001),
        "unit": unit,
        "observation": "",
        "confidence": None,
        "source": "OCR local",
    }


def _match_product_name(name, products):
    if not name:
        return None, 0.0
    exact = globals()["find_product"](products, name)
    if exact:
        return exact, 1.0
    sims = globals()["suggestions"](name, products, limit=3)
    if sims:
        return sims[0][1], float(sims[0][0])
    return None, 0.0


def _ocr_build_candidates(text, products):
    candidates = []
    seen = set()
    _norm = globals()["norm"]
    for line in str(text or "").splitlines():
        parsed = _ocr_parse_line(line)
        if not parsed:
            continue
        key = _norm(parsed["name"])
        if not key or key in seen:
            continue
        seen.add(key)
        best, score = _match_product_name(parsed["name"], products)
        alt_best, alt_score = _match_product_name(parsed.get("alt_name"), products)
        candidates.append({
            **parsed,
            "suggested": best.get("nome") if best else None,
            "score": score,
            "alt_suggested": alt_best.get("nome") if alt_best else None,
            "alt_score": alt_score,
        })
        if len(candidates) >= 50:
            break
    return candidates


def _ai_response_text(body):
    """Extrai o texto retornado pelo Gemini generateContent."""
    if not isinstance(body, dict):
        return ""
    texts = []
    for candidate in body.get("candidates", []) or []:
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        for part in content.get("parts", []) or []:
            if isinstance(part, dict) and part.get("text"):
                texts.append(str(part.get("text")))
    return "\n".join(texts).strip()


def _ai_extract_items(file_bytes, products):
    """Usa Gemini com visão quando configurado. A imagem não é salva no Supabase."""
    import base64 as _base64
    import json as _json
    import re as _re
    import requests as _requests
    from urllib.parse import quote as _urlquote

    api_key = _photo_ai_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada nos Secrets do Streamlit.")

    prepared, mime = _photo_preprocess(file_bytes, for_ai=True)
    encoded_image = _base64.b64encode(prepared).decode("ascii")
    categories = [
        "Mercearia", "Hortifruti", "Carnes", "Bebidas", "Laticínios e ovos",
        "Padaria", "Congelados", "Limpeza", "Higiene pessoal",
        "Casa e utilidades", "Pet", "Infantil", "Saúde e farmácia"
    ]
    prompt = f"""Você está lendo uma lista de compras brasileira a partir de uma foto ou print.
A imagem pode conter LETRA MANUSCRITA, duas colunas, rasuras, quantidades, unidades e alternativas escritas com 'ou'.

Extraia somente itens de compra realmente visíveis. Não invente texto.
Leia todas as colunas de cima para baixo.
Ignore cabeçalhos, NO/DATE, linhas vazias e conteúdo claramente riscado.
Quando uma linha tiver dois produtos separados por 'ou', use o primeiro como principal e o segundo como alternativa.
Quando a linha tiver dois produtos independentes unidos por 'e' ou '/', se for claramente uma solicitação de ambos, gere dois itens.
Quantidades no início devem ser preservadas.
Exemplos:
- '6 leite' => principal 'leite', quantidade 6, unidade 'un'
- '500g acém moído' => principal 'acém moído', quantidade 500, unidade 'g'
- '1kg peito de frango' => principal 'peito de frango', quantidade 1, unidade 'kg'
- 'Uva ou Morango' => principal 'Uva', alternativa 'Morango', quantidade 1
- '1 Fralda depende do preço' => principal 'Fralda', observacao 'depende do preço'
Se algo estiver incerto, mantenha a melhor leitura possível e reduza confianca. Não omita uma linha apenas por estar manuscrita.

Categorias permitidas: {", ".join(categories)}.

Responda APENAS com JSON válido, sem markdown, neste formato:
{{
  "items": [
    {{
      "raw": "texto como aparece",
      "principal": "nome do produto",
      "alternativa": null,
      "quantidade": 1,
      "unidade": "un",
      "categoria": "Mercearia",
      "observacao": "",
      "confianca": 0.95
    }}
  ]
}}
"""

    payload = {
        "contents": [{
            "parts": [
                {
                    "inlineData": {
                        "mimeType": mime,
                        "data": encoded_image,
                    }
                },
                {
                    "text": prompt
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    model = _photo_ai_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{_urlquote(model, safe='.-_')}:generateContent"
    r = _requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json=payload,
        timeout=90,
    )
    if not r.ok:
        msg = r.text[:900]
        raise RuntimeError(f"Falha na leitura por Gemini ({r.status_code}): {msg}")

    body = r.json()
    raw_text = _ai_response_text(body).strip()
    if not raw_text:
        feedback = body.get("promptFeedback") if isinstance(body, dict) else None
        raise RuntimeError(f"O Gemini não retornou conteúdo utilizável. Retorno: {feedback or 'sem detalhes'}")

    raw_text = _re.sub(r"^\s*```(?:json)?\s*", "", raw_text, flags=_re.I)
    raw_text = _re.sub(r"\s*```\s*$", "", raw_text)
    try:
        parsed = _json.loads(raw_text)
    except Exception:
        match = _re.search(r"\{.*\}", raw_text, flags=_re.S)
        if not match:
            raise RuntimeError("O Gemini respondeu, mas não retornou uma estrutura de itens válida.")
        parsed = _json.loads(match.group(0))

    items = parsed.get("items", []) if isinstance(parsed, dict) else []
    candidates = []
    _norm = globals()["norm"]
    seen = set()
    for item in items[:60]:
        if not isinstance(item, dict):
            continue
        principal = str(item.get("principal") or "").strip()
        if not principal:
            continue
        key = _norm(principal)
        if not key:
            continue
        qty = globals()["num"](item.get("quantidade")) or 1.0
        unit = str(item.get("unidade") or "").strip().lower()
        alternative = str(item.get("alternativa") or "").strip() or None
        raw = str(item.get("raw") or principal).strip()
        observation = str(item.get("observacao") or "").strip()
        category = str(item.get("categoria") or "Mercearia").strip() or "Mercearia"
        try:
            confidence = max(0.0, min(1.0, float(item.get("confianca", 0.75))))
        except Exception:
            confidence = 0.75

        dedupe = (_norm(principal), _norm(alternative or ""), round(float(qty), 4), unit)
        if dedupe in seen:
            continue
        seen.add(dedupe)

        best, score = _match_product_name(principal, products)
        alt_best, alt_score = _match_product_name(alternative, products)
        candidates.append({
            "raw": raw,
            "name": principal,
            "alt_name": alternative,
            "qty": max(float(qty), 0.001),
            "unit": unit,
            "category": category,
            "observation": observation,
            "confidence": confidence,
            "source": "Gemini com visão",
            "suggested": best.get("nome") if best else None,
            "score": score,
            "alt_suggested": alt_best.get("nome") if alt_best else None,
            "alt_score": alt_score,
        })
    return candidates, raw_text


def _convert_qty_for_product(qty, extracted_unit, product_unit):
    import unicodedata as _ud

    def clean(v):
        x = _ud.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode().lower().strip()
        x = x.replace(".", "")
        aliases = {
            "grama": "g", "gramas": "g", "gr": "g",
            "quilo": "kg", "quilos": "kg", "kilograma": "kg", "kilogramas": "kg",
            "litro": "l", "litros": "l", "lt": "l",
            "mililitro": "ml", "mililitros": "ml",
            "unidade": "un", "unidades": "un", "und": "un", "unid": "un",
        }
        return aliases.get(x, x)

    src = clean(extracted_unit)
    dst = clean(product_unit)
    value = float(qty or 1)
    if src == "g" and dst == "kg":
        return value / 1000
    if src == "kg" and dst == "g":
        return value * 1000
    if src == "ml" and dst == "l":
        return value / 1000
    if src == "l" and dst == "ml":
        return value * 1000
    return value


def _photo_add_existing(main_product, qty, alt_product=None):
    """Inclui usando a lógica já validada de preço e alternativa quando disponível."""
    import inspect as _inspect

    _num = globals()["num"]
    fn = globals()["add_item"]
    price = _num(main_product.get("ultimo_preco")) or _num(main_product.get("preco_sugerido"))
    alt_price = 0
    if alt_product:
        alt_price = _num(alt_product.get("ultimo_preco")) or _num(alt_product.get("preco_sugerido"))

    params = _inspect.signature(fn).parameters
    supports_alt = any(p.kind == _inspect.Parameter.VAR_POSITIONAL for p in params.values()) or len(params) >= 9
    if alt_product and supports_alt:
        return fn(
            main_product.get("nome"),
            main_product.get("categoria", "Mercearia"),
            main_product.get("unidade", "un."),
            qty,
            price,
            alt_product.get("nome"),
            alt_product.get("categoria", "Mercearia"),
            alt_product.get("unidade", "un."),
            alt_price,
        )
    return fn(
        main_product.get("nome"),
        main_product.get("categoria", "Mercearia"),
        main_product.get("unidade", "un."),
        qty,
        price,
    )


def _clear_ocr_state():
    for key in (
        "photo_import_requested", "photo_ocr_text", "photo_ocr_candidates",
        "photo_import_file", "photo_engine", "photo_ocr_confidence",
        "photo_engine_note", "photo_ai_raw"
    ):
        st.session_state.pop(key, None)
    # Limpa também os widgets dinâmicos da revisão anterior.
    for key in list(st.session_state.keys()):
        if str(key).startswith(("ocr_product_", "ocr_qty_", "ocr_alt_", "ocr_use_alt_", "ocr_new_", "ocr_cat_", "ocr_unit_")):
            st.session_state.pop(key, None)


def _analyze_photo(file_bytes, mode, products):
    local = _ocr_extract_local(file_bytes)
    local_candidates = _ocr_build_candidates(local["text"], products)
    ai_key = _photo_ai_key()

    if mode == "OCR local":
        return {
            "candidates": local_candidates,
            "text": local["text"],
            "engine": "OCR local",
            "ocr_confidence": local["confidence"],
            "note": "Leitura feita sem serviço externo de IA.",
        }

    should_use_ai = mode == "IA para manuscrito"
    if mode == "Automático":
        match_scores = [float(x.get("score") or 0) for x in local_candidates]
        match_quality = (sum(match_scores) / len(match_scores)) if match_scores else 0.0
        strong_matches = sum(1 for x in match_scores if x >= 0.70)
        strong_ratio = strong_matches / len(match_scores) if match_scores else 0.0
        should_use_ai = bool(ai_key) and (
            local["confidence"] < 75
            or len(local_candidates) < 5
            or match_quality < 0.68
            or strong_ratio < 0.60
        )

    if should_use_ai:
        if not ai_key:
            if mode == "IA para manuscrito":
                raise RuntimeError("Para usar visão por IA, configure GEMINI_API_KEY nos Secrets do Streamlit.")
        else:
            try:
                ai_candidates, ai_raw = _ai_extract_items(file_bytes, products)
                if ai_candidates:
                    return {
                        "candidates": ai_candidates,
                        "text": local["text"],
                        "engine": f"Gemini com visão · {_photo_ai_model()}",
                        "ocr_confidence": local["confidence"],
                        "note": "O Gemini interpretou manuscrito, colunas, quantidades e alternativas. Revise antes de incluir.",
                        "ai_raw": ai_raw,
                    }
            except Exception as e:
                if mode == "IA para manuscrito":
                    raise
                return {
                    "candidates": local_candidates,
                    "text": local["text"],
                    "engine": "OCR local (fallback)",
                    "ocr_confidence": local["confidence"],
                    "note": f"A IA não pôde ser usada; mantive o OCR local. Motivo: {e}",
                }

    return {
        "candidates": local_candidates,
        "text": local["text"],
        "engine": "OCR local",
        "ocr_confidence": local["confidence"],
        "note": "O OCR apresentou confiança suficiente; a IA não foi acionada.",
    }


@st.dialog("Adicionar itens por foto ou print", width="large")
def _photo_import_dialog():
    products = globals().get("products", [])
    current = globals().get("current", [])
    _norm = globals()["norm"]
    _num = globals()["num"]

    st.caption("Envie uma foto ou print. O app tenta reconhecer os itens e você revisa tudo antes de incluir.")
    uploaded = st.file_uploader(
        "Foto ou print da lista",
        type=["png", "jpg", "jpeg", "webp"],
        key="photo_import_file",
    )

    ai_available = bool(_photo_ai_key())
    mode = st.radio(
        "Modo de leitura",
        ["Automático", "IA para manuscrito", "OCR local"],
        horizontal=True,
        key="photo_read_mode",
    )
    if ai_available:
        st.caption(f"Gemini disponível ({_photo_ai_model()}). No modo Automático ele só é acionado quando o OCR local estiver fraco.")
    else:
        st.caption("Gemini ainda não configurado. Automático usa OCR local até GEMINI_API_KEY ser adicionada aos Secrets.")

    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True, key="photo_cancel"):
        _clear_ocr_state()
        st.rerun()

    if c2.button("Ler imagem", type="primary", use_container_width=True, key="photo_read"):
        if uploaded is None:
            st.warning("Selecione uma imagem primeiro.")
        else:
            try:
                with st.spinner("Analisando a imagem..."):
                    result = _analyze_photo(uploaded.getvalue(), mode, products)
                st.session_state["photo_ocr_text"] = result.get("text", "")
                st.session_state["photo_ocr_candidates"] = result.get("candidates", [])
                st.session_state["photo_engine"] = result.get("engine", "")
                st.session_state["photo_ocr_confidence"] = result.get("ocr_confidence", 0)
                st.session_state["photo_engine_note"] = result.get("note", "")
                st.session_state["photo_ai_raw"] = result.get("ai_raw", "")
                st.rerun()
            except Exception as e:
                st.error(f"Não consegui ler essa imagem: {e}")

    text = st.session_state.get("photo_ocr_text", "")
    candidates = st.session_state.get("photo_ocr_candidates") or []
    engine = st.session_state.get("photo_engine", "")
    ocr_conf = float(st.session_state.get("photo_ocr_confidence") or 0)
    note = st.session_state.get("photo_engine_note", "")

    if engine:
        m1, m2 = st.columns(2)
        m1.metric("Leitura utilizada", engine)
        m2.metric("Confiança OCR local", f"{ocr_conf:.0f}%")
        if note:
            st.info(note)

    if text:
        with st.expander("Texto bruto do OCR local", expanded=False):
            st.text(text[:7000])

    ai_raw = st.session_state.get("photo_ai_raw", "")
    if ai_raw:
        with st.expander("Estrutura interpretada pela IA", expanded=False):
            st.code(ai_raw[:9000], language="json")

    if candidates:
        st.markdown("#### Revisar itens encontrados")
        st.caption("Nada entra na lista sem sua confirmação. Produtos alternativos reconhecidos com 'ou' também podem ser revisados.")
        names = [p.get("nome", "") for p in products if p.get("nome")]
        by_name = {_norm(p.get("nome")): p for p in products}
        categories = sorted(set(
            ["Mercearia", "Hortifruti", "Carnes", "Bebidas", "Laticínios e ovos", "Padaria", "Congelados",
             "Limpeza", "Higiene pessoal", "Casa e utilidades", "Pet", "Infantil", "Saúde e farmácia"]
            + [str(p.get("categoria") or "Mercearia") for p in products]
        ))
        options = ["— Ignorar —", "— Selecionar produto —", "— Cadastrar como novo —"] + names
        alt_options = ["— Sem alternativa —"] + names
        selected_rows = []

        for i, candidate in enumerate(candidates):
            confidence = candidate.get("confidence")
            conf_label = f" · confiança IA {float(confidence):.0%}" if confidence is not None else ""
            st.markdown(f"**Reconhecido:** {candidate.get('raw') or candidate.get('name')}{conf_label}")
            if candidate.get("alt_name"):
                st.caption(f"Alternativa reconhecida: {candidate['alt_name']}")
            if candidate.get("observation"):
                st.caption(f"Observação: {candidate['observation']}")

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

            chosen_product = by_name.get(_norm(choice)) if choice in names else None
            base_qty = float(candidate.get("qty") or 1)
            if chosen_product:
                base_qty = _convert_qty_for_product(base_qty, candidate.get("unit"), chosen_product.get("unidade"))
            qty = b.number_input(
                "Qtd",
                min_value=0.001,
                value=max(float(base_qty), 0.001),
                step=1.0 if float(base_qty).is_integer() else 0.1,
                format="%.3f" if abs(float(base_qty) - round(float(base_qty), 2)) > 1e-9 else "%.2f",
                key=f"ocr_qty_{i}",
            )

            row = None
            if choice == "— Cadastrar como novo —":
                n1, n2, n3 = st.columns([2, 1.4, 1])
                new_name = n1.text_input("Nome do novo produto", value=candidate.get("name") or "", key=f"ocr_new_{i}")
                suggested_cat = candidate.get("category") or "Mercearia"
                cat_index = categories.index(suggested_cat) if suggested_cat in categories else 0
                new_cat = n2.selectbox("Categoria", categories, index=cat_index, key=f"ocr_cat_{i}")
                new_unit = n3.text_input("Unidade", value=(candidate.get("unit") or "un."), key=f"ocr_unit_{i}")
                if new_name.strip() and new_unit.strip():
                    row = {"mode": "new", "name": new_name.strip(), "category": new_cat, "unit": new_unit.strip(), "qty": qty, "alt": None}
            elif chosen_product:
                use_alt_default = bool(candidate.get("alt_name") or candidate.get("alt_suggested"))
                use_alt = st.checkbox("Usar produto alternativo", value=use_alt_default, key=f"ocr_use_alt_{i}")
                alt_product = None
                if use_alt:
                    default_alt = candidate.get("alt_suggested")
                    alt_index = alt_options.index(default_alt) if default_alt in alt_options else 0
                    alt_choice = st.selectbox("Alternativa", alt_options, index=alt_index, key=f"ocr_alt_{i}")
                    if alt_choice != "— Sem alternativa —":
                        alt_product = by_name.get(_norm(alt_choice))
                row = {"mode": "existing", "product": chosen_product, "qty": qty, "alt": alt_product}

            if row:
                selected_rows.append(row)
            st.divider()

        if st.button("Adicionar itens selecionados", type="primary", use_container_width=True, key="ocr_add_selected"):
            if not selected_rows:
                st.warning("Selecione pelo menos um produto.")
            else:
                try:
                    current_keys = {_norm(x.get("nome_produto")) for x in current}
                    added = 0
                    skipped = []
                    for row in selected_rows:
                        if row["mode"] == "new":
                            name = row["name"]
                            key = _norm(name)
                            if key in current_keys:
                                skipped.append(name)
                                continue
                            existing = globals()["find_product"](products, name)
                            if existing:
                                ok = _photo_add_existing(existing, row["qty"])
                            else:
                                globals()["create_product"](name, row["category"], row["unit"], 0, row["qty"])
                                globals()["clear"]()
                                ok = globals()["add_item"](name, row["category"], row["unit"], row["qty"], 0)
                            if ok is not False:
                                current_keys.add(key)
                                added += 1
                            else:
                                skipped.append(name)
                            continue

                        p = row["product"]
                        key = _norm(p.get("nome"))
                        if key in current_keys:
                            skipped.append(p.get("nome"))
                            continue
                        ok = _photo_add_existing(p, row["qty"], row.get("alt"))
                        if ok is not False:
                            current_keys.add(key)
                            added += 1
                        else:
                            skipped.append(p.get("nome"))

                    _clear_ocr_state()
                    if skipped:
                        st.session_state["photo_import_result"] = (
                            f"{added} item(ns) adicionado(s). {len(skipped)} ignorado(s), principalmente por duplicidade."
                        )
                    else:
                        st.session_state["photo_import_result"] = f"{added} item(ns) adicionado(s) pela imagem."
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao incluir os itens: {e}")
    elif engine:
        st.warning("Não encontrei itens suficientes. Tente IA para manuscrito ou envie uma foto mais próxima e nítida.")


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
