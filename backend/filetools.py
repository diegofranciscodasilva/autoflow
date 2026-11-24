"""Ferramentas de arquivos: organizar por tipo, renomear em lote e mesclar planilhas."""
import io
import re
import unicodedata
import zipfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath

import pandas as pd

import processor as proc

# Categoria -> extensões. Nomes de pasta sem acento, para ficarem portáveis em qualquer sistema.
CATEGORIES = {
    "Imagens": {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "heic"},
    "Documentos": {"pdf", "doc", "docx", "txt", "rtf", "odt", "md"},
    "Planilhas": {"xls", "xlsx", "csv", "ods"},
    "Apresentacoes": {"ppt", "pptx", "odp", "key"},
    "Audio": {"mp3", "wav", "ogg", "m4a", "flac"},
    "Videos": {"mp4", "mov", "avi", "mkv", "webm"},
    "Compactados": {"zip", "rar", "7z", "tar", "gz"},
    "Codigo": {"py", "js", "html", "css", "json", "xml", "sql", "ts"},
}
ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def category_for(ext: str) -> str:
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return "Outros"


def clean_filename(name: str) -> str:
    """Remove caminhos (evita path traversal) e caracteres inválidos do nome."""
    base = PurePosixPath(str(name or "").replace("\\", "/")).name
    base = ILLEGAL.sub("", base).strip(". ")
    return base or "arquivo"


def unique(path: str, used: set) -> str:
    """Garante caminho único dentro do .zip: 'a.txt' -> 'a (2).txt'."""
    p = PurePosixPath(path)
    cand, n = path, 2
    while cand.lower() in used:
        cand = str(p.parent / f"{p.stem} ({n}){p.suffix}") if str(p.parent) != "." else f"{p.stem} ({n}){p.suffix}"
        n += 1
    used.add(cand.lower())
    return cand


def _month(modified: list, i: int) -> str:
    try:
        return datetime.fromtimestamp(float(modified[i]) / 1000).strftime("%Y-%m")
    except (IndexError, ValueError, TypeError, OSError):
        return datetime.now().strftime("%Y-%m")


# ============ ORGANIZAR ============
def organize_files(files, mode: str = "type", modified=None):
    modified = modified or []
    used, items, folders = set(), [], {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, f in enumerate(files):
            name = clean_filename(f.filename)
            ext = Path(name).suffix.lower().lstrip(".")
            top = category_for(ext)
            folder = f"{top}/{_month(modified, i)}" if mode == "type_month" else top
            dest = unique(f"{folder}/{name}", used)
            z.writestr(dest, f.read())
            items.append({"from": name, "to": dest})
            folders[top] = folders.get(top, 0) + 1
        z.writestr("relatorio_organizacao.csv",
                   proc.rows_to_csv_bytes(["original", "destino"], [[i["from"], i["to"]] for i in items]))
    return buf.getvalue(), {"total": len(items), "folders": folders, "items": items}


# ============ RENOMEAR ============
def normalize_name(text: str, case: str, spaces: str, remove_accents: bool) -> str:
    if remove_accents:
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    if spaces == "underscore":
        text = re.sub(r"\s+", "_", text.strip())
    text = ILLEGAL.sub("", text)
    if case == "lower":
        text = text.lower()
    return text.strip(". ") or "arquivo"


def rename_files(files, pattern, start=1, pad=3, case="keep", spaces="underscore", remove_accents=True):
    pattern = (pattern or "").strip()
    if not pattern or len(pattern) > 100:
        raise ValueError("Informe um padrão de nome com até 100 caracteres.")
    today = date.today().isoformat()
    used, items = set(), []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, f in enumerate(files):
            original = clean_filename(f.filename)
            p = Path(original)
            base = (pattern.replace("{nome}", p.stem)
                           .replace("{n}", str(start + i).zfill(pad))
                           .replace("{data}", today))
            new = unique(normalize_name(base, case, spaces, remove_accents) + p.suffix.lower(), used)
            z.writestr(new, f.read())
            items.append({"from": original, "to": new})
        z.writestr("mapa_renomeacao.csv",
                   proc.rows_to_csv_bytes(["original", "novo_nome"], [[i["from"], i["to"]] for i in items]))
    return buf.getvalue(), {"total": len(items), "items": items}


# ============ MESCLAR PLANILHAS ============
def merge_tables(files, add_origin: bool = True):
    if len(files) < 2:
        raise ValueError("Selecione pelo menos 2 planilhas para mesclar.")

    canon, frames, per_file, presence = {}, [], [], {}
    for f in files:
        df = proc.read_table(f)
        # Colunas equivalentes (ex.: "Preço" e "preco") viram uma só, com o nome da primeira ocorrência
        df = df.rename(columns={c: canon.setdefault(proc.slug(c), c) for c in df.columns})
        if df.columns.duplicated().any():
            raise ValueError(f'"{f.filename}" tem colunas com nomes equivalentes.')
        for c in df.columns:
            presence[c] = presence.get(c, 0) + 1
        name = clean_filename(f.filename)
        if add_origin:
            if "arquivo_origem" in df.columns:
                raise ValueError(f'"{f.filename}" já possui uma coluna "arquivo_origem".')
            df.insert(0, "arquivo_origem", name)
        per_file.append({"name": name, "rows": len(df)})
        frames.append(df)

    merged = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    if len(merged) > proc.MAX_ROWS:
        raise ValueError("O resultado passa do limite de linhas.")
    missing = [c for c, n in presence.items() if n < len(files)]
    return merged, {"files": per_file, "missing": missing}
