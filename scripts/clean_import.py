#!/usr/bin/env python
"""Filter a django-ical prod backup, rejecting malicious uploads."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# Ensure the project root (parent of this scripts/ dir) is on sys.path so
# that django_myical and mycalendar packages can be found when the script is
# invoked directly (e.g. python scripts/clean_import.py).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import django
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile


def _validate(path: Path) -> tuple[bool, str]:
    from mycalendar.validators import validate_csv_upload
    if not path.exists():
        return False, "file not found on disk"
    if not path.is_file():
        return False, "not a regular file"
    try:
        data = path.read_bytes()
    except OSError as exc:
        return False, f"read error: {exc}"
    uploaded = SimpleUploadedFile(name=path.name, content=data, content_type="text/csv")
    try:
        validate_csv_upload(uploaded)
    except ValidationError as exc:
        return False, "; ".join(exc.messages)
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src-dir", required=True, type=Path)
    parser.add_argument("--dst-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    src = args.src_dir.resolve()
    dst = args.dst_dir.resolve()
    src_db = src / "db.sqlite3"
    src_media = src / "media"

    if not src_db.exists():
        print(f"error: {src_db} not found", file=sys.stderr)
        return 1
    if not src_media.exists():
        print(f"error: {src_media} not found", file=sys.stderr)
        return 1

    if not args.dry_run:
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "media" / "documents").mkdir(parents=True, exist_ok=True)
        (dst / "media" / "ics").mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_db, dst / "db.sqlite3")

    db_for_django = (dst if not args.dry_run else src) / "db.sqlite3"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_myical.settings")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_for_django}"
    os.environ.setdefault("DJANGO_SECRET_KEY", "clean-import-script-not-for-runtime")
    os.environ.setdefault("DJANGO_DEBUG", "True")
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost")
    os.environ.setdefault("DJANGO_SITE_DOMAIN", "localhost")
    os.environ.setdefault("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost")
    django.setup()

    from mycalendar.models import MyCalendar

    kept_rows = 0
    dropped_rows = 0
    files_kept = 0
    rejected: list[tuple[str, str]] = []
    rows_to_delete: list[int] = []

    for obj in MyCalendar.objects.all():
        doc_path = src_media / obj.document.name
        ok, reason = _validate(doc_path)
        if not ok:
            rejected.append((str(obj.document.name), reason))
            dropped_rows += 1
            rows_to_delete.append(obj.pk)
            continue

        if not args.dry_run:
            dst_doc = dst / "media" / obj.document.name
            dst_doc.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(doc_path, dst_doc)
        files_kept += 1
        kept_rows += 1

        if obj.ics and obj.ics.name:
            ics_path = src_media / obj.ics.name
            if ics_path.exists():
                if not args.dry_run:
                    dst_ics = dst / "media" / obj.ics.name
                    dst_ics.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ics_path, dst_ics)
                files_kept += 1
            else:
                if not args.dry_run:
                    obj.ics = None
                    obj.save(update_fields=["ics"])

    if not args.dry_run and rows_to_delete:
        MyCalendar.objects.filter(pk__in=rows_to_delete).delete()

    print(f"\n=== clean_import {'DRY RUN' if args.dry_run else 'APPLIED'} ===")
    print(f"src: {src}")
    print(f"dst: {dst}")
    print(f"rows kept:    {kept_rows}")
    print(f"rows dropped: {dropped_rows}")
    print(f"files kept:   {files_kept}")
    print(f"files rejected: {len(rejected)}")
    if rejected:
        print("\nrejected files:")
        for name, reason in rejected:
            print(f"  - {name}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
