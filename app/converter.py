import tempfile, subprocess, os
from weasyprint import HTML
from jinja2 import Template

def html_to_pdf_bytes(html_content: str) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
    try:
        HTML(string=html_content).write_pdf(tmp_path)
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        try: os.remove(tmp_path)
        except Exception: pass
    return data

def libreoffice_convert_bytes(input_bytes: bytes, filename: str) -> bytes:
    ext = os.path.splitext(filename)[1].lower()
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, filename)
        with open(input_path, "wb") as f:
            f.write(input_bytes)
        subprocess.run([
            "libreoffice", "--headless", "--convert-to", "pdf", input_path, "--outdir", tmpdir
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        pdf_candidates = [f for f in os.listdir(tmpdir) if f.lower().endswith(".pdf")]
        if not pdf_candidates: raise RuntimeError("No se generó el PDF")
        pdf_path = os.path.join(tmpdir, pdf_candidates[0])
        with open(pdf_path, "rb") as f:
            return f.read()

def render_template(template_str: str, context: dict | None) -> str:
    tmpl = Template(template_str)
    return tmpl.render(**(context or {}))
