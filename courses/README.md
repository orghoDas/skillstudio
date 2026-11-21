# courses

Catalogue and course content: categories, tags, courses, modules, lessons and lesson resources.

## Models
- **`Course`**: `status` moves through `draft` → `under_review` → `published` (or back to `draft` when rejected), then `archived`.
  - The slug is generated from the title and never equals a fixed `/api/courses/<word>/` route (`RESERVED_COURSE_SLUGS`).
  - `is_free=True` forces `price=0` on save.
- **`Module`** and **`Lesson`** are ordered by `position`.
  - A lesson's `content_type` is `video`, `text` or `quiz`.
  - Video URLs are parsed by `video.parse_video_url` and must be YouTube or Vimeo.
  - `is_free` lessons can be previewed without buying the course.
- **`CourseVersion`** is kept for `Course.current_version`. Nothing writes versions yet.

## Who can see what: `policies.py`
Use these functions; don't re-check enrollment or ownership in views.

| Function | True when |
|---|---|
| `can_manage_course` | the user owns the course or is a platform admin |
| `can_view_course_catalog` | the course is published, or the user can manage it |
| `can_access_course_content` | the course is free, the user manages it, or the user has an `active`/`completed` enrollment |
| `can_access_lesson` | the lesson is free, or `can_access_course_content` |

Lesson **order** (which lesson is unlocked) is a separate rule: `enrollments.services.lesson_lock_state`.

## Rules
- Content can be deleted only while the course is a draft. Published history belongs to students.
- `services.validate_course_for_submission` decides whether a draft can go to review. An admin publishes or rejects it.
- The catalogue list accepts only allow-listed `ordering` values. It also filters by comma-separated `category`/`level`, duration buckets and a numeric instructor id.
- `python manage.py create_categories` seeds the categories.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apicourses). That file is generated from the URLconf, so it is always current.
