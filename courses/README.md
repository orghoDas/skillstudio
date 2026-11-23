# courses

Catalogue and course content: categories, tags, courses, modules, lessons and lesson resources.

## Models
- **`Category`** generates a unique slug from its name when saved without one. Renames keep the existing slug. The public category list counts published courses.
- **`Course`**: `status` moves through `draft` → `under_review` → `published` (or back to `draft` when rejected), then `archived`.
  - The slug is generated from the title and never equals a fixed `/api/courses/<word>/` route (`RESERVED_COURSE_SLUGS`).
  - A free course has a zero price. A paid course has a positive price. The API validates both fields together and the database enforces the pair.
- **`Module`** and **`Lesson`** are ordered by `position`.
  - A lesson's `content_type` is `video`, `text` or `quiz`.
  - Video URLs are parsed by `video.parse_video_url` and support YouTube, Vimeo and direct video files such as MP4 and WebM.
  - `is_free` lessons can be previewed without buying the course.
- **`CourseVersion`** records the published course details and curriculum. `Course.current_version` points to the snapshot for that catalog entry. A revision is a separate course linked by `revision_of`.

## Who can see what: `policies.py`
Use these functions; don't re-check enrollment or ownership in views.

| Function | True when |
|---|---|
| `can_manage_course` | the user owns the course or is a platform admin |
| `can_view_course_catalog` | the course is published, the user can manage it, or the user has an `active`/`completed` enrollment in an archived course |
| `can_access_course_content` | the user manages the course, the published course is free, or the user has an `active`/`completed` enrollment in a published or archived course |
| `can_access_lesson` | the lesson is a free preview of a visible course, or the user can access the course content |

Lesson **order** (which lesson is unlocked) is a separate rule: `enrollments.services.lesson_lock_state`.

## Rules
- The course instructor and platform admins can manage eligible courses, modules, and lessons. Management requests from other authenticated users return HTTP 403. An admin edit keeps the assigned instructor.
- Catalog responses identify instructors by ID and profile display name. Instructors see review feedback and the review date on My Courses and the course content page until they resubmit. Review feedback in the API is restricted to the course owner and platform admins.
- The content editor creates drafts and submits them for platform admin review. Draft submission and publishing both require at least one module, with a lesson in each module.
- Editing course details or adding, editing, or deleting a module or lesson returns a course under review to draft. Resubmit it after editing. Whole-course deletion is available for drafts.
- A course owner or platform admin can open a draft revision from the published course's content page. The revision copies course content, quizzes, and question banks. Copied final exams start as drafts. Each published course can have one successor.
- Course writes validate `tag_ids` against existing tags and collapse duplicates. Omitting the list keeps the current tags. An empty list clears them.
- Publishing the revision archives the previous catalog entry. Existing enrollments, purchases, and progress stay with the previous version. The revision has its own slug and receives new enrollments. Owners and platform admins can also archive a published course directly.
- Django admin shows course records and review actions. The course editor handles content changes and revisions.
- Course lists accept `page_size` with a default of 20 and a maximum of 100. The catalog also filters by comma-separated `category`/`level`, duration buckets, and a numeric instructor ID. `ordering=popular` ranks courses by active and completed enrollments. Requests for rating order return HTTP 400.
- Migration `courses/0007` converts legacy assignment and resource lessons to text. Their existing lesson IDs, content, and attachments carry over.
- `python manage.py create_categories` seeds the categories.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apicourses). That file is generated from the URLconf, so it is always current.
