import json
import shutil
import uuid
from pathlib import Path

from django.conf import settings


SESSION_KEY = "finanzas_importaciones_documentos"


def _session_bucket(request):
    return request.session.setdefault(SESSION_KEY, {})


def guardar_importacion_temporal(request, *, xml_file=None, pdf_file=None, payload=None):
    token = uuid.uuid4().hex
    base_dir = Path(settings.MEDIA_ROOT) / "finanzas" / "importaciones_tmp" / token
    base_dir.mkdir(parents=True, exist_ok=True)
    payload_serializable = json.loads(json.dumps(payload or {}, default=str))
    info = {"payload": payload_serializable, "files": {}}
    if xml_file:
        xml_path = base_dir / xml_file.name
        with xml_path.open("wb") as output:
            for chunk in xml_file.chunks():
                output.write(chunk)
        info["files"]["xml"] = {"path": str(xml_path), "name": xml_file.name}
    if pdf_file:
        pdf_path = base_dir / pdf_file.name
        with pdf_path.open("wb") as output:
            for chunk in pdf_file.chunks():
                output.write(chunk)
        info["files"]["pdf"] = {"path": str(pdf_path), "name": pdf_file.name}
    bucket = _session_bucket(request)
    bucket[token] = info
    request.session.modified = True
    return token


def cargar_importacion_temporal(request, token):
    return _session_bucket(request).get(token)


def actualizar_payload_importacion(request, token, payload):
    bucket = _session_bucket(request)
    if token in bucket:
        bucket[token]["payload"] = payload
        request.session.modified = True


def eliminar_importacion_temporal(request, token):
    bucket = _session_bucket(request)
    info = bucket.pop(token, None)
    request.session.modified = True
    if not info:
        return
    files = info.get("files", {})
    path = None
    if files.get("xml"):
        path = Path(files["xml"]["path"]).parent
    elif files.get("pdf"):
        path = Path(files["pdf"]["path"]).parent
    if path and path.exists():
        shutil.rmtree(path, ignore_errors=True)
