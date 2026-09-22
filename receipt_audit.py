"""Leitura independente e conferência de preços reais (sem gravação na compra)."""

import base64
import io
import json
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill


def norm(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]+", " ", value.encode("ascii", "ignore").decode().lower()).strip()


def money(value):
    value = amount(value)
    if value is None:
        return "—"
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def amount(value):
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        if isinstance(value, str):
            raw = value.strip().replace("R$", "").replace("\u00a0", "").replace(" ", "")
            if "," in raw and "." in raw:
                raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
            elif "," in raw:
                raw = raw.replace(",", ".")
            value = raw
        number = Decimal(str(value))
        return number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def quantity(value):
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        raw = str(value).strip().replace(" ", "").replace(",", ".")
        number = Decimal(raw)
        return number if number.is_finite() and number > 0 and number < 1000000 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _text(value):
    return "" if value is None else str(value).strip()


_HEADERS = {
    "name": ("produto", "descricao", "descrição", "nome", "nome produto", "item", "mercadoria"),
    "qty": ("quantidade", "qtd", "qtde", "qnt", "quant"),
    "unit": ("preco unitario pago", "preço unitário pago", "preço unitário", "preco unitario",
             "valor unitario", "valor unitário", "preco real unitario", "preço real unitário",
             "preço real", "preco real"),
    "total": ("total pago", "total da linha", "valor total", "subtotal", "valor pago total",
              "valor total pago", "total do item"),
}


def read_prices_excel(raw):
    """Aceita planilhas livres com produto e uma coluna monetária inequívoca."""
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise ValueError("Envie um arquivo .xlsx de até 8 MB.")
    lookup = {norm(alias): key for key, names in _HEADERS.items() for alias in names}
    try:
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("O Excel não pôde ser aberto. Use um arquivo .xlsx válido.") from exc
    try:
        sheet = header = header_row = None
        for ws in wb.worksheets:
            for i, cells in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row or 1, 20),
                                                    values_only=True), start=1):
                found = {}
                for col, value in enumerate(cells):
                    key = lookup.get(norm(value))
                    if key and key not in found:
                        found[key] = col
                if "name" in found and ("unit" in found or "total" in found):
                    sheet, header, header_row = ws, found, i
                    break
            if sheet is not None:
                break
        if sheet is None:
            raise ValueError("A planilha precisa ter PRODUTO e PREÇO UNITÁRIO PAGO ou TOTAL PAGO. Baixe o modelo do aplicativo.")

        lines = []
        ignored = []
        for row_number, cells in enumerate(sheet.iter_rows(min_row=header_row + 1, values_only=True),
                                           start=header_row + 1):
            def cell(key):
                pos = header.get(key)
                return cells[pos] if pos is not None and pos < len(cells) else None

            name = _text(cell("name"))
            if not name:
                continue
            if len(lines) >= 150:
                raise ValueError("Há mais de 150 linhas de produtos. Divida a planilha.")
            unit, total, qty = amount(cell("unit")), amount(cell("total")), quantity(cell("qty"))
            if unit is None and total is None:
                ignored.append(str(row_number))
                continue
            if (unit is not None and unit < 0) or (total is not None and total < 0):
                ignored.append(str(row_number))
                continue
            if _text(cell("qty")) and qty is None:
                ignored.append(str(row_number))
                continue
            lines.append({"name": name, "qty": str(qty) if qty is not None else None,
                          "unit_price": str(unit) if unit is not None else None,
                          "line_total": str(total) if total is not None else None})
        if not lines:
            raise ValueError("Não foram encontrados produtos com preços válidos.")
        warning = (f"{len(ignored)} linha(s) com preço/quantidade inválido(s) ignorada(s): "
                   + ", ".join(ignored[:8])) if ignored else ""
        return {"lines": lines, "grand_total": None, "warning": warning, "source": "Excel"}
    finally:
        wb.close()


def read_receipt_gemini(raw, mime_type, api_key, models):
    """Envia imagem/PDF apenas ao Gemini; não armazena o comprovante."""
    if not api_key:
        raise ValueError("Configure GEMINI_API_KEY para ler fotos e PDFs. O Excel funciona sem Gemini.")
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise ValueError("Envie uma imagem ou PDF de até 8 MB.")
    if mime_type not in ("image/png", "image/jpeg", "image/webp", "application/pdf"):
        raise ValueError("Formato inválido. Envie PNG, JPG, WEBP ou PDF.")

    prompt = """Leia um comprovante/cupom fiscal brasileiro de supermercado.
Retorne SOMENTE JSON válido:
{"items":[{"produto":"nome como impresso","quantidade":1,
"preco_unitario":"1.09","total_linha":"5.45"}],
"total_documento":"123.45","observacao":""}
Extraia apenas linhas de produtos efetivamente comprados; não inclua cabeçalhos, forma de pagamento,
troco, tributos, totalizadores, CPF, CNPJ, dados pessoais, nem itens cancelados.
Cada produto deve ter exatamente uma linha, preservando repetições e quantidade decimal quando houver.
preco_unitario significa preço por unidade ou por kg do cupom; total_linha significa valor efetivo
daquela linha depois de descontos identificáveis. total_documento é o TOTAL FINAL da compra, não o
valor entregue em dinheiro ou da parcela. Transcreva valores em reais, com ponto decimal e sem R$.
Se algum campo monetário ou quantidade não estiver legível, use null. Não invente números.
Não distribua descontos globais entre produtos. Em observacao, sinalize descontos globais,
cancelamentos e partes ilegíveis, sem dados pessoais."""
    payload = {"contents": [{"parts": [
        {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(raw).decode("ascii")}},
        {"text": prompt},
    ]}], "generationConfig": {"responseMimeType": "application/json"}}
    errors = []
    for model in dict.fromkeys(m for m in models if m):
        try:
            from urllib.parse import quote
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='.-_')}:generateContent"
            response = requests.post(url, headers={"Content-Type": "application/json",
                                                   "x-goog-api-key": api_key},
                                     json=payload, timeout=90)
            if not response.ok:
                errors.append(f"{model}: HTTP {response.status_code}")
                continue
            body = response.json()
            message = "\n".join(
                part.get("text", "") for candidate in body.get("candidates", [])
                for part in candidate.get("content", {}).get("parts", [])
                if isinstance(part, dict) and part.get("text")
            )
            message = re.sub(r"^\s*'''(?:json)?\s*|\s*'''\s*$", "", message.strip())
            message = re.sub(r"^\s*"+chr(96)*3+r"(?:json)?\s*|\s*"+chr(96)*3+r"\s*$", "", message)
            result = json.loads(message)
            items = result.get("items", []) if isinstance(result, dict) else []
            if not isinstance(items, list):
                raise ValueError("A resposta não contém uma lista de produtos.")
            if len(items) > 150:
                raise ValueError("O comprovante tem mais de 150 linhas; separe-o em arquivos menores.")
            lines = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = _text(item.get("produto"))
                qty = quantity(item.get("quantidade"))
                unit = amount(item.get("preco_unitario"))
                total = amount(item.get("total_linha"))
                if name and (unit is not None or total is not None) and (unit is None or unit >= 0) and (total is None or total >= 0):
                    lines.append({"name": name, "qty": str(qty) if qty else None,
                                  "unit_price": str(unit) if unit is not None else None,
                                  "line_total": str(total) if total is not None else None})
            if not lines:
                raise ValueError("Não identifiquei produtos com preços legíveis no comprovante.")
            grand_total = amount(result.get("total_documento"))
            return {"lines": lines, "grand_total": str(grand_total) if grand_total is not None else None,
                    "warning": _text(result.get("observacao")), "source": f"Gemini · {model}"}
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{model}: {type(exc).__name__}")
    raise ValueError("Não consegui interpretar o comprovante. Confira a legibilidade ou utilize Excel. "
                     + ("; ".join(errors[:3]) if errors else ""))


def price_model(items):
    """Modelo com os produtos da compra e campos de valores reais em branco."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Preços reais"
    ws.append(("PRODUTO", "QUANTIDADE", "PREÇO UNITÁRIO PAGO", "TOTAL PAGO"))
    for item in items:
        name = _text(item.get("produto_escolhido") or item.get("nome_produto"))
        # Evita interpretar conteúdo da planilha como fórmula Excel.
        if name.startswith(("=", "+", "-", "@")):
            name = "'" + name
        ws.append((name, float(quantity(item.get("quantidade")) or 1), None, None))
    for i, width in enumerate((43, 19, 25, 24), start=1):
        ws.column_dimensions[chr(64 + i)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:D{max(ws.max_row, 2)}"
    for cell in ws[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="2563EB")
        cell.alignment = Alignment(horizontal="center")
    guide = wb.create_sheet("Instruções")
    for line in (
        "Preencha PREÇO UNITÁRIO PAGO e/ou TOTAL PAGO com valores reais, não estimados.",
        "Cada linha deve representar um produto do cupom. Você pode incluir linhas extras.",
        "QUANTIDADE deve ser a quantidade no comprovante (incluindo frações para produtos a peso).",
        "Se for recebido um Excel de outro sistema, mantenha cabeçalhos equivalentes.",
        "A conferência é apenas visual; ela NÃO modifica os valores já lançados na compra.",
    ):
        guide.append((line,))
    guide.column_dimensions["A"].width = 105
    result = io.BytesIO()
    wb.save(result)
    return result.getvalue()


def compare(lines, current, choices, grand_total=None):
    """Conferência por centavos; itens repetidos do cupom são agregados por vínculo."""
    by_id = {str(item.get("id")): item for item in current}
    grouped = defaultdict(list)
    extras = []
    for index, line in enumerate(lines):
        target = str(choices.get(index) or "")
        if target not in by_id:
            extras.append(line["name"])
        else:
            grouped[target].append(line)

    results = []
    verified_total = Decimal("0.00")
    app_confirmed_total = sum(
        (quantity(item.get("quantidade")) or Decimal(0)) * (amount(item.get("preco_unitario")) or Decimal(0))
        for item in current if item.get("confirmado")
    )
    for key, item in by_id.items():
        if not item.get("confirmado") and key not in grouped:
            continue
        name = _text(item.get("produto_escolhido") or item.get("nome_produto"))
        app_qty = quantity(item.get("quantidade"))
        app_unit = amount(item.get("preco_unitario"))
        app_total = (app_qty * app_unit).quantize(Decimal(".01")) if app_qty and app_unit is not None else None
        entries = grouped.get(key, [])
        if not entries:
            results.append({"produto": name, "status": "Não encontrado no comprovante",
                            "qtd_app": str(app_qty or ""), "qtd_doc": "—",
                            "preco_app": money(app_unit), "preco_doc": "—",
                            "total_app": money(app_total), "total_doc": "—", "diferenca": "—"})
            continue
        qties = [quantity(x.get("qty")) for x in entries]
        q_doc = sum(qties) if all(q is not None for q in qties) else None
        totals = []
        for x in entries:
            line_total = amount(x.get("line_total"))
            unit = amount(x.get("unit_price"))
            qty = quantity(x.get("qty"))
            if line_total is None and unit is not None and qty is not None:
                line_total = (unit * qty).quantize(Decimal(".01"))
            totals.append(line_total)
        receipt_total = sum(totals) if all(v is not None for v in totals) else None
        receipt_unit = (receipt_total / q_doc).quantize(Decimal(".01")) if receipt_total is not None and q_doc else (
            amount(entries[0].get("unit_price")) if len(entries) == 1 else None)
        price_diff = (receipt_total - app_total).quantize(Decimal(".01")) if receipt_total is not None and app_total is not None else None
        qty_ok = q_doc is not None and app_qty == q_doc
        if not item.get("confirmado"):
            status = "Pendente no aplicativo"
        elif q_doc is not None and not qty_ok:
            status = "Quantidade diferente"
        elif price_diff is not None and price_diff != 0:
            status = "Total divergente"
        elif receipt_unit is not None and app_unit is not None and (
                receipt_unit - app_unit).copy_abs() > Decimal(".01") and len(entries) == 1:
            status = "Preço unitário divergente"
        elif receipt_total is not None and qty_ok and price_diff == 0:
            status = "Confere"
        else:
            status = "Conferência incompleta"
        if receipt_total is not None:
            verified_total += receipt_total
        results.append({"produto": name, "status": status, "qtd_app": str(app_qty or ""),
                        "qtd_doc": str(q_doc) if q_doc is not None else "—",
                        "preco_app": money(app_unit), "preco_doc": money(receipt_unit),
                        "total_app": money(app_total), "total_doc": money(receipt_total),
                        "diferenca": money(price_diff) if price_diff is not None else "—"})
    return {"results": results, "extras": extras,
            "app_confirmed_total": app_confirmed_total,
            "linked_receipt_total": verified_total,
            "grand_total": amount(grand_total),
            "matched": len(lines) - len(extras)}
