"""Funções de apoio compartilhadas."""
import re
import unicodedata


def slugify(text: str) -> str:
    """'Relatório Final 2026' -> 'relatorio_final_2026' (sem acentos, minúsculas, com underscore)."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "arquivo"
