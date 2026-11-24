"""API Flask do AutoFlow: tratamento de planilhas e organização de arquivos."""
import io
import json
import os

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

import files
import sheets

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # limite total de upload: 15 MB


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "Arquivo acima do limite permitido."}), 413


def parse_rules() -> list:
    """Lê as regras enviadas pelo formulário e descarta qualquer valor fora da lista permitida."""
    try:
        raw = json.loads(request.form.get("rules", "[]"))
    except json.JSONDecodeError:
        raw = []
    return [r for r in raw if r in sheets.ALLOWED_RULES] if isinstance(raw, list) else []


def load_uploaded_sheet():
    """Valida o upload e carrega a planilha. Retorna (DataFrame, None) ou (None, resposta de erro)."""
    f = request.files.get("file")
    if not f or not f.filename:
        return None, (jsonify({"error": "Envie uma planilha."}), 400)
    try:
        return sheets.load_table(f), None
    except ValueError as e:
        return None, (jsonify({"error": str(e)}), 400)
    except Exception:
        return None, (jsonify({"error": "Não foi possível ler o arquivo. Verifique se ele não está corrompido."}), 400)


@app.post("/api/sheet/interpret")
def sheet_interpret():
    text = (request.get_json(silent=True) or {}).get("text", "")
    return jsonify({"rules": sheets.interpret(str(text)[:500])})


@app.post("/api/sheet/process")
def sheet_process():
    df, error = load_uploaded_sheet()
    if error:
        return error
    result, log = sheets.apply_rules(df, parse_rules())
    return jsonify({
        "rows_before": len(df),
        "rows_after": len(result),
        "columns": [str(c) for c in result.columns],
        "preview": sheets.preview(result),
        "log": log,
    })


@app.post("/api/sheet/download")
def sheet_download():
    df, error = load_uploaded_sheet()
    if error:
        return error
    fmt = request.form.get("format", "csv")
    if fmt not in ("csv", "xlsx"):
        return jsonify({"error": "Formato inválido."}), 400
    result, _ = sheets.apply_rules(df, parse_rules())
    content, mimetype = sheets.export(result, fmt)
    return send_file(io.BytesIO(content), mimetype=mimetype,
                     as_attachment=True, download_name=f"planilha_tratada.{fmt}")


@app.post("/api/files/organize")
def files_organize():
    uploaded = [f for f in request.files.getlist("files") if f.filename]
    if not uploaded:
        return jsonify({"error": "Envie ao menos um arquivo."}), 400
    zip_buffer = files.organize(
        uploaded,
        prefix_date=request.form.get("prefix_date") == "true",
        make_slug=request.form.get("slugify") == "true",
    )
    return send_file(zip_buffer, mimetype="application/zip",
                     as_attachment=True, download_name="arquivos_organizados.zip")


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
    