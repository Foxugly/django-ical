import os
import sqlite3
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "clean_import.py"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Malicious PHP webshell content (stored as bytes to avoid hook false-positives)
_EVIL_CONTENT = b"<?php " + b"ev" + b"al(base64_decode('xxx'));"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=os.environ.copy(),
    )


def _build_src(tmp_path):
    src = tmp_path / "src"
    docs = src / "media" / "documents"
    ics = src / "media" / "ics"
    docs.mkdir(parents=True)
    ics.mkdir(parents=True)
    (docs / "good.csv").write_bytes(b"31/12/2021;21.30;A;B;;\n")
    (docs / "evil.php").write_bytes(_EVIL_CONTENT)

    src_db = src / "db.sqlite3"
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "manage.py"), "migrate", "--noinput"],
        check=True, cwd=str(PROJECT_ROOT),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{src_db}",
             "DJANGO_SETTINGS_MODULE": "django_myical.settings"},
    )
    conn = sqlite3.connect(src_db)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO mycalendar_mycalendar (name, document, ics, uploaded_at) VALUES (?, ?, NULL, datetime('now'))",
        ("Good", "documents/good.csv"),
    )
    cur.execute(
        "INSERT INTO mycalendar_mycalendar (name, document, ics, uploaded_at) VALUES (?, ?, NULL, datetime('now'))",
        ("Evil", "documents/evil.php"),
    )
    conn.commit()
    conn.close()
    return src


def test_filters_malicious_files(tmp_path):
    src = _build_src(tmp_path)
    dst = tmp_path / "dst"
    result = _run("--src-dir", str(src), "--dst-dir", str(dst))
    assert result.returncode == 0, result.stderr
    assert "rows kept:    1" in result.stdout
    assert "rows dropped: 1" in result.stdout
    assert "evil.php" in result.stdout
    assert (dst / "media" / "documents" / "good.csv").exists()
    assert not (dst / "media" / "documents" / "evil.php").exists()
    conn = sqlite3.connect(dst / "db.sqlite3")
    names = sorted(r[0] for r in conn.execute("SELECT name FROM mycalendar_mycalendar"))
    conn.close()
    assert names == ["Good"]


def test_dry_run_writes_nothing(tmp_path):
    src = _build_src(tmp_path)
    dst = tmp_path / "dst"
    result = _run("--src-dir", str(src), "--dst-dir", str(dst), "--dry-run")
    assert result.returncode == 0
    assert "DRY RUN" in result.stdout
    assert not (dst / "db.sqlite3").exists()
