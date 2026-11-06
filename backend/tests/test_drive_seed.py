import unittest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import Course, Lesson
from app.modules.learning.drive_seed import COURSE_ID, DriveCourseSeed, drive_file_id, seed_drive_course
from test_domain_api import DomainApiFixture


class DriveSeedTests(DomainApiFixture):
    def manifest(self):
        return DriveCourseSeed(title='Seed test', videos=[
            {'url': f'https://drive.google.com/file/d/example_video_{index:010d}/view'} for index in range(10)])

    def test_exactly_ten_real_distinct_links_are_required(self):
        with self.assertRaises(ValidationError):
            DriveCourseSeed(title='Missing videos', videos=[])
        values = self.manifest().model_dump()
        values['videos'][1] = values['videos'][0]
        with self.assertRaises(ValidationError):
            DriveCourseSeed.model_validate(values)
        for url in ['https://drive.google.com/drive/folders/abcdefghijk', 'https://example.com/file/d/abcdefghijk/view', 'https://drive.google.com.evil.example/file/d/abcdefghijk/view']:
            with self.assertRaises(ValueError):
                drive_file_id(url)

    def test_seed_is_atomic_idempotent_and_does_not_invent_video_duration(self):
        manifest = self.manifest()
        with self.assertRaises(RuntimeError):
            with self.factory.begin() as session:
                seed_drive_course(session, manifest)
                raise RuntimeError('Rollback')
        with self.factory.begin() as session:
            self.assertIsNone(session.get(Course, COURSE_ID))
            course, created = seed_drive_course(session, manifest)
            self.assertTrue(created)
        with self.factory.begin() as session:
            _, created = seed_drive_course(session, manifest)
            self.assertFalse(created)
            self.assertEqual(session.scalar(select(func.count()).select_from(Lesson).where(Lesson.course_id == COURSE_ID)), 10)
            self.assertIsNone(session.scalar(select(Lesson.duration_minutes).where(Lesson.course_id == COURSE_ID)))

    def test_unknown_duration_can_be_acknowledged_without_setting_trusted_grades(self):
        with self.factory.begin() as session:
            seed_drive_course(session, self.manifest())
        sub = self.purchase({'id': str(COURSE_ID)})
        lessons = self.request('GET', f"/subscriptions/{sub['id']}/lessons")
        self.assertEqual(len(lessons), 10)
        for lesson in lessons:
            result = self.request('POST', f"/subscriptions/{sub['id']}/lessons/{lesson['id']}/watch", {'duration_watched': 0, 'completed': True})
        self.assertEqual(result['progress_percent'], '99.99')
        self.assertIsNone(result['final_score'])
        self.assertIsNone(result['result'])


if __name__ == '__main__':
    unittest.main()
