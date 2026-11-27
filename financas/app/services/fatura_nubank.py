"""Leitura do CSV da fatura do Nubank. Só compras parceladas entram; pagamentos e estornos são descartados."""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

PARCELA_RE = re.compile(r"Parcela\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
LIMPA_RE = re.compile(r"\s*-?\s*Parcela\s+\d+\s*/\s*\d+", re.IGNORECASE)
IGNORAR_RE = re.compile(r"pagamento|pagto|estorno", re.IGNORECASE)


@dataclass
class LinhaFatura:
    data: date  # data da compra
    nome_original: str  # título como vem no CSV (usado para reconhecer duplicidades)
    nome: str  # título limpo, sem "Parcela x/y"
    parcela: int  # parcela atual, como aparece na fatura
    total: int  # total de parcelas
    valor_cents: int  # valor de cada parcela (ou da compra à vista)
    parcelado: bool = True  # False: compra à vista (vencimento), só para registro


def decodifica(conteudo: bytes) -> str:
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ValueError("Arquivo não está em um formato de texto conhecido")


def valor_para_centavos(texto: str) -> int:
    t = texto.strip().replace("R$", "").replace(" ", "").replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(t)
    except InvalidOperation:
        raise ValueError(f"Valor inválido: {texto!r}")
    return int((valor * 100).to_integral_value())


def data_iso(texto: str) -> date:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    raise ValueError(f"Data inválida: {texto!r}")


def limpa_nome(titulo: str) -> str:
    return " ".join(LIMPA_RE.sub("", titulo).split())


def chave_nome(nome: str) -> str:
    return " ".join(nome.lower().split())


def _ler(conteudo: bytes, so_parcelados: bool) -> list[LinhaFatura]:
    texto = decodifica(conteudo)
    primeira = texto.splitlines()[0] if texto.strip() else ""
    separador = ";" if primeira.count(";") > primeira.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=separador)
    colunas = {c.strip().lower(): c for c in (leitor.fieldnames or [])}
    if not {"date", "title", "amount"} <= set(colunas):
        raise ValueError("CSV sem as colunas date, title e amount")

    linhas: list[LinhaFatura] = []
    for row in leitor:
        titulo = (row[colunas["title"]] or "").strip()
        if not titulo or IGNORAR_RE.search(titulo):
            continue
        texto_valor = (row[colunas["amount"]] or "").strip()
        if texto_valor.startswith("-"):
            continue
        valor = valor_para_centavos(texto_valor)
        if valor <= 0:
            continue
        m = PARCELA_RE.search(titulo)
        if m:
            parcela, total = int(m.group(1)), int(m.group(2))
            if not 1 <= parcela <= total:
                continue
            parcelado = True
        else:
            if so_parcelados:
                continue
            parcela, total, parcelado = 0, 0, False
        linhas.append(
            LinhaFatura(
                data=data_iso(row[colunas["date"]]),
                nome_original=titulo,
                nome=limpa_nome(titulo),
                parcela=parcela,
                total=total,
                valor_cents=valor,
                parcelado=parcelado,
            )
        )
    return linhas


def ler_fatura(conteudo: bytes) -> list[LinhaFatura]:
    """Só as compras parceladas (usado pelo cadastro de parcelados)."""
    return _ler(conteudo, so_parcelados=True)


def ler_fatura_completa(conteudo: bytes) -> list[LinhaFatura]:
    """Todas as compras da fatura, parceladas e à vista. Pagamentos, estornos e créditos saem."""
    return _ler(conteudo, so_parcelados=False)
