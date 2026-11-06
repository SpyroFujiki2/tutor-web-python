"""Create one course from ten Drive video links, without changing Drive sharing."""

import argparse
from pathlib import Path

from pydantic import ValidationError

from app.core.config import get_database_settings
from app.core.database import create_database_engine, create_session_factory
from app.modules.learning.drive_seed import DriveCourseSeed, seed_drive_course


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'seed' / 'drive-course.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        manifest = DriveCourseSeed.model_validate_json(args.manifest.read_text(encoding='utf-8-sig'))
    except (ValidationError, OSError) as error:
        raise SystemExit('Seed cần manifest hợp lệ chứa đúng 10 link video thật. ' + str(error)) from None
    if args.dry_run:
        print(f'Valid seed: {len(manifest.videos)} videos; no database changes.')
        return
    engine = create_database_engine(get_database_settings())
    try:
        with create_session_factory(engine).begin() as session:
            course, created = seed_drive_course(session, manifest)
            identity = course.id
        print(f'Course {identity}: {"created" if created else "already present"}; 10 lessons.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
