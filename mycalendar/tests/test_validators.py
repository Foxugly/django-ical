import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from mycalendar.validators import validate_csv_upload


def _f(name, data, ct="text/csv"):
    return SimpleUploadedFile(name, data, content_type=ct)


def test_accepts_small_csv():
    validate_csv_upload(_f("ok.csv", b"31/12/2021;21.30;A;B;;\n"))


def test_rejects_wrong_extension():
    with pytest.raises(ValidationError, match="extension"):
        validate_csv_upload(_f("evil.exe", b"data"))


def test_rejects_oversized():
    big = b"a" * (1024 * 1024 + 1)  # 1 MiB + 1 byte
    with pytest.raises(ValidationError, match="size"):
        validate_csv_upload(_f("big.csv", big))


def test_rejects_wrong_content_type():
    with pytest.raises(ValidationError, match="content type"):
        validate_csv_upload(_f("ok.csv", b"data", ct="application/x-msdownload"))


def test_rejects_non_text_bytes():
    with pytest.raises(ValidationError, match="binary"):
        validate_csv_upload(_f("nul.csv", b"\x00\x01\x02\xff", ct="text/csv"))
