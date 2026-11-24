"""Motor de automação de planilhas: leitura, etapas de transformação, relatório e exportação."""
import csv
import io
import re
import unicodedata

import pandas as pd

MAX_ROWS = 100_000  # limite de linhas por planilha


# ============ UTILIDADES ============
def plain(text: str) -> str:
    """Minúsculas e sem acentos (usado para comparar textos)."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return t.lower()


def slug(text: str) -> str:
    """Transforma 'Preço Total' em 'preco_total'."""
    t = re.sub(r"[^a-z0-9]+", "_", plain(text)).strip("_")
    return t or "coluna"


def _empty_mask(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")


def _parse_num(v):
    """Converte '1.234,56', 'R$ 10,5' ou '1,234.56' em float. Retorna None se não for número.

    Limitação: '1.234' é lido como 1.234 (decimal), pois não há como distinguir de milhar.
    """
    if v is None:
        return None
    s = str(v).strip().replace("R$", "").replace("%", "").replace(" ", "").replace("\u00a0", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")  # formato brasileiro
        else:
            s = s.replace(",", "")                    # formato americano
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def to_num(series: pd.Series) -> pd.Series:
    return series.map(_parse_num).astype("float64")


def _col(df: pd.DataFrame, name: str) -> str:
    """Encontra a coluna pelo nome exato ou equivalente (ignora acentos, caixa e símbolos)."""
    if name in df.columns:
        return name
    target = slug(name)
    for c in df.columns:
        if slug(c) == target:
            return c
    raise ValueError(f'Coluna não encontrada: "{name}"')


# ============ LEITURA ============
def read_table(storage) -> pd.DataFrame:
    """Lê CSV ou XLSX (primeira aba) como texto, preservando os valores originais."""
    name = (storage.filename or "").lower()
    raw = storage.read()

    if name.endswith(".csv"):
        text = None
        for enc in ("utf-8-sig", "latin-1"):  # latin-1 aceita qualquer byte, então é o último recurso
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        first = text.split("\n", 1)[0]
        sep = ";" if first.count(";") > first.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    elif name.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(raw), dtype=str, engine="openpyxl").fillna("")
    else:
        raise ValueError("Formato não suportado. Use .csv ou .xlsx.")

    if len(df.columns) == 0:
        raise ValueError("A planilha está vazia.")
    if len(df) > MAX_ROWS:
        raise ValueError(f"A planilha tem mais de {MAX_ROWS:,} linhas.".replace(",", "."))
    df.columns = [str(c).strip() or f"coluna_{i + 1}" for i, c in enumerate(df.columns)]
    return df


# ============ ETAPAS ============
def step_trim(df, p):
    changed = 0
    for c in df.columns:
        if df[c].dtype == object:
            new = df[c].map(lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v)
            changed += int((new != df[c]).sum())
            df[c] = new
    return df, f"Espaços extras removidos em {changed} célula(s)."


def step_remove_empty(df, p):
    mask = pd.concat([_empty_mask(df[c]) for c in df.columns], axis=1).all(axis=1)
    removed = int(mask.sum())
    return df[~mask].reset_index(drop=True), f"{removed} linha(s) vazia(s) removida(s)."


def step_remove_duplicates(df, p):
    cols = [_col(df, c) for c in (p.get("columns") or [])] or None
    before = len(df)
    df = df.drop_duplicates(subset=cols).reset_index(drop=True)
    return df, f"{before - len(df)} duplicata(s) removida(s)."


def step_standardize_headers(df, p):
    seen, new = {}, []
    for c in df.columns:
        s = slug(c)
        seen[s] = seen.get(s, 0) + 1
        new.append(s if seen[s] == 1 else f"{s}_{seen[s]}")
    df.columns = new
    return df, "Cabeçalhos padronizados (minúsculas, sem acentos, com _)."


def step_parse_number(df, p):
    c = _col(df, p.get("column", ""))
    nonempty = ~_empty_mask(df[c])
    nums = to_num(df[c])
    invalid = int((nums.isna() & nonempty).sum())
    df[c] = nums
    return df, f'Coluna "{c}" convertida para número ({invalid} valor(es) inválido(s) ficaram vazios).'


def step_text_case(df, p):
    c = _col(df, p.get("column", ""))
    fn = {"upper": str.upper, "lower": str.lower, "title": str.title}.get(p.get("mode"))
    if not fn:
        raise ValueError("Formato de texto inválido.")
    df[c] = df[c].map(lambda v: fn(v) if isinstance(v, str) else v)
    return df, f'Coluna "{c}" ajustada.'


def step_fill_empty(df, p):
    c = _col(df, p.get("column", ""))
    value = str(p.get("value", ""))
    df[c] = df[c].astype(object)
    mask = _empty_mask(df[c])
    df.loc[mask, c] = value
    return df, f'{int(mask.sum())} célula(s) vazia(s) de "{c}" preenchida(s).'


def step_filter(df, p):
    c = _col(df, p.get("column", ""))
    op = p.get("op")
    val = str(p.get("value", "")).strip()
    s = df[c]

    if op == "equals":
        mask = s.astype(str).str.strip().str.casefold() == val.casefold()
    elif op == "contains":
        mask = s.astype(str).str.contains(val, case=False, regex=False, na=False)
    elif op in ("gt", "gte", "lt", "lte"):
        num = _parse_num(val)
        if num is None:
            raise ValueError("Informe um número válido para comparar.")
        n = to_num(s)
        mask = {"gt": n > num, "gte": n >= num, "lt": n < num, "lte": n <= num}[op]
    elif op == "not_empty":
        mask = ~_empty_mask(s)
    elif op == "is_empty":
        mask = _empty_mask(s)
    else:
        raise ValueError("Condição de filtro inválida.")

    kept = df[mask].reset_index(drop=True)
    return kept, f'Filtro em "{c}": {len(kept)} linha(s) mantida(s), {len(df) - len(kept)} removida(s).'


def step_sort(df, p):
    c = _col(df, p.get("column", ""))
    asc = p.get("order", "asc") != "desc"
    nonempty = ~_empty_mask(df[c])
    nums = to_num(df[c])
    # Se a maioria dos valores é numérica, ordena como número; senão, como texto
    if nonempty.sum() and nums.notna().sum() >= 0.8 * nonempty.sum():
        key = nums
    else:
        key = df[c].astype(str).str.casefold()
    key = key.where(nonempty)  # vazios sempre vão para o fim
    order = key.sort_values(ascending=asc, na_position="last").index
    return df.loc[order].reset_index(drop=True), f'Ordenado por "{c}" ({"crescente" if asc else "decrescente"}).'


def step_drop_columns(df, p):
    cols = [_col(df, c) for c in (p.get("columns") or [])]
    if not cols:
        raise ValueError("Escolha ao menos uma coluna.")
    return df.drop(columns=cols), f"Coluna(s) excluída(s): {', '.join(cols)}."


# Lista fechada de operações permitidas: nada de código arbitrário
STEPS = {
    "trim": step_trim,
    "remove_empty": step_remove_empty,
    "remove_duplicates": step_remove_duplicates,
    "standardize_headers": step_standardize_headers,
    "parse_number": step_parse_number,
    "text_case": step_text_case,
    "fill_empty": step_fill_empty,
    "filter": step_filter,
    "sort": step_sort,
    "drop_columns": step_drop_columns,
}


def run_steps(df: pd.DataFrame, steps: list):
    """Aplica as etapas em ordem e devolve (DataFrame final, log)."""
    if not isinstance(steps, list) or not steps:
        raise ValueError("Adicione ao menos uma etapa.")
    if len(steps) > 20:
        raise ValueError("Use no máximo 20 etapas por fluxo.")

    df = df.copy()
    log = []
    for i, step in enumerate(steps, start=1):
        fn = STEPS.get(step.get("type") if isinstance(step, dict) else None)
        if not fn:
            raise ValueError(f"Etapa {i}: operação desconhecida.")
        try:
            df, message = fn(df, step)
        except ValueError as e:
            raise ValueError(f"Etapa {i}: {e}") from e
        log.append({"type": step["type"], "message": message, "rows": len(df)})
    return df, log


# ============ ANÁLISE E PRÉVIA ============
def describe(df: pd.DataFrame) -> list:
    """Resumo por coluna: vazios, valores únicos e, se numérica, mínimo/máximo/média/soma."""
    out = []
    for c in df.columns:
        s = df[c]
        empty = _empty_mask(s)
        nums = to_num(s)
        filled = int((~empty).sum())
        info = {"name": c, "empty": int(empty.sum()), "unique": int(s[~empty].astype(str).nunique()), "numeric": None}
        if filled and nums.notna().sum() >= 0.8 * filled:
            info["numeric"] = {
                "min": float(nums.min()), "max": float(nums.max()),
                "mean": round(float(nums.mean()), 2), "sum": round(float(nums.sum()), 2),
            }
        out.append(info)
    return out


def preview(df: pd.DataFrame, n: int = 8) -> dict:
    return {"columns": [str(c) for c in df.columns], "rows": df.head(n).fillna("").astype(str).values.tolist()}


# ============ COMANDO EM LINGUAGEM NATURAL (regras simples) ============
def _find_col(fragment: str, columns: list):
    """Acha a coluna mencionada primeiro no trecho (a mais longa vence em caso de empate)."""
    best = None
    for c in columns:
        p = plain(c)
        pos = fragment.find(p)
        if p and pos >= 0:
            cand = (pos, -len(p), c)
            best = cand if best is None or cand < best else best
    return best[2] if best else None


def parse_command(text: str, columns: list) -> list:
    """Converte um texto em etapas. Reconhece apenas padrões conhecidos; o resto é ignorado."""
    t = plain(text)
    steps = []

    if re.search(r"espaco|trim", t):
        steps.append({"type": "trim"})
    if re.search(r"linhas? (vazias?|em branco)", t):
        steps.append({"type": "remove_empty"})
    if re.search(r"cabecalho|padroniz\w* (as )?colunas", t):
        steps.append({"type": "standardize_headers"})
    if re.search(r"duplicat|duplicad", t):
        steps.append({"type": "remove_duplicates"})

    m = re.search(
        r"filtr\w*\s+(.+?)\s+(maior ou igual a|menor ou igual a|maior que|menor que|igual a|contem)\s+([^,]+?)(?=\s+e\s+(?:remov|orden|padron|limp)|,|$)", t)
    if m:
        col = _find_col(m.group(1), columns)
        op = {"maior ou igual a": "gte", "menor ou igual a": "lte", "maior que": "gt",
              "menor que": "lt", "igual a": "equals", "contem": "contains"}[m.group(2)]
        if col:
            steps.append({"type": "filter", "column": col, "op": op, "value": m.group(3).strip()})

    m = re.search(r"ordenar|ordene\w*|classific\w*", t)
    if m:
        frag = t[m.end():]
        col = _find_col(frag, columns)
        if col:
            desc = re.search(r"decrescente|maior para o menor|do maior", frag)
            steps.append({"type": "sort", "column": col, "order": "desc" if desc else "asc"})

    return steps


# ============ EXPORTAÇÃO ============
def safe_cell(v):
    """Evita CSV/Excel injection: textos que começam com = + @ (ou - não numérico) viram texto literal."""
    if isinstance(v, str) and v:
        if v[0] in ("=", "+", "@") or (v[0] == "-" and _parse_num(v) is None):
            return "'" + v
    return v


def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.map(safe_cell)
    out.columns = [safe_cell(str(c)) for c in out.columns]
    return out


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    # ';' e UTF-8 com BOM: abre corretamente no Excel em português
    return sanitize(df).to_csv(index=False, sep=";").encode("utf-8-sig")


def to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        sanitize(df).to_excel(writer, index=False, sheet_name="Dados")
    return buf.getvalue()


def rows_to_csv_bytes(header: list, rows: list) -> bytes:
    """CSV simples (para relatórios dentro dos .zip), também protegido contra injection."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    for r in rows:
        w.writerow([safe_cell(v) for v in r])
    return buf.getvalue().encode("utf-8-sig")
