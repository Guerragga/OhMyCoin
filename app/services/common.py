from __future__ import annotations

import calendar
import ipaddress
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional
from urllib.parse import urlparse

from config import Config

TIPOS_CATEGORIA = {"receita", "despesa", "geral"}
TIPOS_MOVIMENTACAO = {"receita", "despesa"}
TIPOS_CONTA = {"corrente", "poupanca", "carteira", "digital", "investimento", "outros"}
FORMAS_PAGAMENTO = {"conta", "cartao"}
TEMAS = {"claro", "escuro"}
CHART_FLAGS = [
    "mostrar_grafico_real_previsto",
    "mostrar_grafico_categorias",
    "mostrar_grafico_evolucao",
    "mostrar_grafico_forma_pagamento",
    "mostrar_grafico_contas",
    "mostrar_grafico_cartoes",
]
MAX_DINHEIRO = Decimal("9999999999.99")


def hoje() -> date:
    return date.today()


def mes_atual() -> str:
    return hoje().strftime("%Y-%m")


def normalizar_mes(valor: Optional[str]) -> str:
    texto = (valor or mes_atual()).strip()
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", texto) or not 1900 <= int(texto[:4]) <= 9799:
        raise ValueError("Mês inválido. Use o formato AAAA-MM entre 1900 e 9799.")
    try:
        datetime.strptime(texto + "-01", "%Y-%m-%d")
    except ValueError:
        raise ValueError("Mês inválido. Use o formato AAAA-MM.") from None
    return texto


def inicio_fim_mes(ano_mes: Optional[str] = None):
    ano_mes = normalizar_mes(ano_mes)
    inicio = datetime.strptime(f"{ano_mes}-01", "%Y-%m-%d").date()
    if inicio.month == 12:
        fim = date(inicio.year + 1, 1, 1)
    else:
        fim = date(inicio.year, inicio.month + 1, 1)
    return ano_mes, inicio, fim


def ultimo_dia_mes(ano: int, mes: int) -> int:
    return calendar.monthrange(ano, mes)[1]


def data_por_dia(ano_mes: str, dia: int) -> date:
    base = datetime.strptime(ano_mes + "-01", "%Y-%m-%d").date()
    dia = max(1, min(int(dia or 1), ultimo_dia_mes(base.year, base.month)))
    return date(base.year, base.month, dia)


def somar_meses(data_base: date, meses: int) -> date:
    mes = data_base.month - 1 + meses
    ano = data_base.year + mes // 12
    mes = mes % 12 + 1
    dia = min(data_base.day, ultimo_dia_mes(ano, mes))
    return date(ano, mes, dia)


def decimal_brl(valor, campo="valor", permite_zero=False) -> Decimal:
    if valor is None:
        raise ValueError(f"{campo} é obrigatório.")
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if texto == "":
        texto = "0" if permite_zero else ""
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        numero = Decimal(texto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{campo} deve ser numérico.") from None
    if not numero.is_finite():
        raise ValueError(f"{campo} deve ser numérico e finito.")
    if numero > MAX_DINHEIRO:
        raise ValueError(f"{campo} ultrapassa o limite permitido.")
    if permite_zero:
        if numero < 0:
            raise ValueError(f"{campo} não pode ser negativo.")
    elif numero <= 0:
        raise ValueError(f"{campo} deve ser maior que zero.")
    return numero


def inteiro(valor, campo, minimo=0, maximo=9999):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{campo} deve ser numérico.") from None
    if numero < minimo or numero > maximo:
        raise ValueError(f"{campo} deve estar entre {minimo} e {maximo}.")
    return numero


def parse_data(valor, padrao: Optional[date] = None) -> date:
    if not valor:
        return padrao or hoje()
    try:
        result = datetime.strptime(str(valor), "%Y-%m-%d").date()
        if not 1900 <= result.year <= 9799:
            raise ValueError("Data fora do intervalo permitido.")
        return result
    except ValueError:
        raise ValueError("Data inválida.") from None


def texto_obrigatorio(valor, campo, limite=None):
    texto = (valor or "").strip()
    if not texto:
        raise ValueError(f"{campo} é obrigatório.")
    if limite and len(texto) > limite:
        raise ValueError(f"{campo} deve ter no máximo {limite} caracteres.")
    return texto


def texto_opcional(valor, limite=None):
    texto = (valor or "").strip()
    if limite and len(texto) > limite:
        raise ValueError(f"Texto deve ter no máximo {limite} caracteres.")
    return texto or None


def validar_email(email: str) -> str:
    email = texto_obrigatorio(email, "E-mail", 120).lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("E-mail inválido.")
    return email


def validar_senha(senha: str):
    if not isinstance(senha, str) or not senha:
        raise ValueError("Senha é obrigatória.")
    minimo = Config.PASSWORD_MIN_LENGTH
    if len(senha) < minimo:
        raise ValueError(f"A senha precisa ter pelo menos {minimo} caracteres.")
    if len(senha) > 128:
        raise ValueError("A senha deve ter no máximo 128 caracteres.")
    if not re.search(r"[A-Za-zÀ-ÿ]", senha) or not re.search(r"\d", senha):
        raise ValueError("A senha precisa combinar letras e números.")
    return senha


def validar_emoji(valor):
    emoji = (valor or "💰").strip()
    if len(emoji) > 8:
        raise ValueError("Use apenas um emoji curto como foto de perfil.")
    # Bloqueia texto comum longo e tags HTML. Não tenta validar todos os emojis do Unicode, mas evita abuso.
    if any(ch in emoji for ch in "<>/\\"):
        raise ValueError("Emoji inválido.")
    return emoji or "💰"


def validar_url_imagem(valor):
    url = texto_opcional(valor, 500)
    if not url:
        return None
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        raise ValueError("URL de imagem inválida.") from None
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError("Use uma URL HTTPS pública, sem credenciais e na porta padrão.")
    if any(c.isspace() for c in url) or "\\" in url:
        raise ValueError("URL de imagem inválida.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip:
        if not ip.is_global:
            raise ValueError("URL de imagem não pode apontar para rede privada/local.")
    elif (
        "." not in host
        or host.endswith((".local", ".localhost", ".internal", ".test"))
        or not re.fullmatch(r"[a-z0-9.-]+", host)
        or not re.search(r"[a-z]", host.rsplit(".", 1)[-1])
    ):
        raise ValueError("URL de imagem deve apontar para um host público.")
    # Only emitted as <img src>; the server never resolves or fetches this URL.
    return url


def normalizar_tema(valor):
    tema = (valor or "escuro").strip().lower()
    return tema if tema in TEMAS else "escuro"
