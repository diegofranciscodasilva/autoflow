"""Organização de arquivos em pastas por tipo, gerando um ZIP em memória."""
import io
import os
import zipfile
from datetime import date

from werkzeug.utils import secure_filename

from utils import slugify

CATEGORIES = {
    "Documentos": {".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf"},
    "Planilhas": {".xls", ".xlsx", ".csv", ".ods"},
    "Apresentacoes": {".ppt", ".pptx", ".odp"},
    "Imagens": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "Audio_Video": {".mp3", ".wav", ".mp4", ".mov", ".avi", ".mkv"},
    "Compactados": {".zip", ".rar", ".7z"},
}


def category_of(ext: str) -> str:
    for folder, exts in CATEGORIES.items():
        if ext in exts:
            return folder
    return "Outros"


def organize(files, prefix_date=False, make_slug=False) -> io.BytesIO:
    """Distribui os arquivos por pasta e inclui um RELATORIO.txt com cada movimentação."""
    buf = io.BytesIO()
    used = set()
    report = ["RELATORIO DE ORGANIZACAO", f"Data: {date.today().isoformat()}", ""]

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            original = secure_filename(f.filename or "") or "arquivo"
            stem, ext = os.path.splitext(original)
            ext = ext.lower()

            new_stem = slugify(stem) if make_slug else stem
            if prefix_date:
                new_stem = f"{date.today().isoformat()}_{new_stem}"

            folder = category_of(ext)
            path = f"{folder}/{new_stem}{ext}"

            # Evita sobrescrever nomes iguais: nome_1, nome_2...
            n = 1
            while path in used:
                path = f"{folder}/{new_stem}_{n}{ext}"
                n += 1
            used.add(path)

            zf.writestr(path, f.read())
            report.append(f"{original}  ->  {path}")

        report += ["", f"Total: {len(used)} arquivo(s)"]
        zf.writestr("RELATORIO.txt", "\n".join(report))

    buf.seek(0)
    return buf
