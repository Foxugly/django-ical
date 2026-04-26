from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

MAX_UPLOAD_BYTES = 1024 * 1024  # 1 MiB
ALLOWED_EXTENSIONS = {".csv", ".txt"}
ALLOWED_CONTENT_TYPES = {"text/csv", "text/plain", "application/csv", "application/vnd.ms-excel"}


def validate_csv_upload(uploaded_file) -> None:
    name = uploaded_file.name.lower()
    if not any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise ValidationError("unsupported file extension; expected .csv or .txt")

    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"file size exceeds {MAX_UPLOAD_BYTES} bytes")

    ct = (getattr(uploaded_file, "content_type", None) or "").lower()
    if ct and ct not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"unsupported content type: {ct}")

    # Binary-content check only applies to freshly-uploaded files (UploadedFile
    # subclasses: InMemoryUploadedFile, TemporaryUploadedFile, SimpleUploadedFile).
    # FieldFile objects (already-saved model files) are skipped here.
    if not isinstance(uploaded_file, UploadedFile):
        return

    head = uploaded_file.read(4096)
    uploaded_file.seek(0)
    if b"\x00" in head:
        raise ValidationError("file appears to be binary, not text")
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        try:
            head.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ValidationError("file is not valid UTF-8 or Latin-1 text") from exc
