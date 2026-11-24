"""Tratamento de planilhas com regras pré-definidas (lista permitida)."""
import io
import re

import pandas as pd

from utils import slugify

# Única lista de operações aceitas: nada fora dela é executado
ALLOWED_RULES = {
    "trim", "remove_empty", "remove_duplicates",
    "title_case", "normalize_columns", "fill_missing",
}

# Palavras-chave -> regra. Ponto de troca: substituir interpret() por uma chamada a um LLM
# que devolva a mesma lista de regras (sempre filtrada por ALLOWED_RULES).
KEYWORDS = {
    "trim": ["espaço", "espaco", "espaços", "trim"],
    "remove_empty": ["linha vazia", "linhas vazias", "linha em branco", "linhas em branco"],
    "remove_duplicates": ["duplicad", "repetid"],
    "title_case": ["maiúscula", "maiuscula", "capitaliz", "padronizar nome"],
    "normalize_columns": ["cabeçalho", "cabecalho", "nome das colunas", "nomes das colunas"],
    "fill_missing": ["preench"],
}


def interpret(text: str) -> list:
    """Converte um comando em texto em uma lista de regras (por palavras-chave)."""
    text = text.lower()
    return [rule for rule, words in KEYWORDS.items() if any(w in text for w in words)]


def load_table(storage) -> pd.DataFrame:
    """Lê CSV ou XLSX como texto, para não alterar valores (ex.: CPFs com zero à esquerda)."""
    name = (storage.filename or "").lower()
    data = storage.read()
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Arquivo acima do limite de 10 MB.")
    if name.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(data), dtype=object)
    if name.endswith(".csv"):
        for enc in ("utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(data), sep=None, engine="python",
                                   encoding=enc, dtype=object)
            except UnicodeDecodeError:
                continue
    raise ValueError("Formato não suportado. Use .csv ou .xlsx.")


def apply_rules(df: pd.DataFrame, rules: list):
    """Aplica as regras em ordem fixa e devolve (DataFrame, log de ações)."""
    rules = [r for r in rules if r in ALLOWED_RULES]
    df = df.copy()
    log = []

    if "normalize_columns" in rules:
        df.columns = [slugify(c) for c in df.columns]
        log.append("Cabeçalhos padronizados")

    if "trim" in rules:
        df = df.apply(lambda col: col.map(
            lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v))
        log.append("Espaços extras removidos")

    if "remove_empty" in rules:
        before = len(df)
        df = df.replace(r"^\s*$", pd.NA, regex=True).dropna(how="all")
        log.append(f"{before - len(df)} linha(s) vazia(s) removida(s)")

    if "title_case" in rules:
        for col in df.columns:
            def title_preserving_emails(value):
                if not isinstance(value, str):
                    return value
                email_pattern = r"[^\s@]+@[^\s@]+\.[^\s@]+"
                parts = re.split(f"({email_pattern})", value)
                return "".join(
                    part if re.fullmatch(email_pattern, part) else part.title()
                    for part in parts
                )

            df[col] = df[col].map(title_preserving_emails)
        log.append("Maiúsculas padronizadas (colunas de e-mail preservadas)")

    if "remove_duplicates" in rules:
        before = len(df)
        df = df.drop_duplicates()
        log.append(f"{before - len(df)} linha(s) duplicada(s) removida(s)")

    if "fill_missing" in rules:
        empties = int(df.isna().sum().sum())
        df = df.fillna("N/D")
        log.append(f"{empties} campo(s) vazio(s) preenchido(s) com N/D")

    return df.reset_index(drop=True), log


def preview(df: pd.DataFrame, n: int = 8) -> list:
    """Primeiras linhas como texto, para exibir na tabela."""
    return df.head(n).fillna("").astype(str).values.tolist()


def export(df: pd.DataFrame, fmt: str):
    """Gera o arquivo final em memória. Retorna (bytes, mimetype)."""
    if fmt == "xlsx":
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        return buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    # CSV com ';' e BOM: abre corretamente no Excel em português
    return df.to_csv(index=False, sep=";").encode("utf-8-sig"), "text/csv"
