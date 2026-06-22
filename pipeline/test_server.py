"""Tests for the LinkedIn pipeline server."""

import json
import os
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import TestCase, main

# Patch BASE before importing server functions
import server

SAMPLE_POST = """\
---
type: text
visibility: PUBLIC
tags: [test, demo]
---

This is a test post body.
"""

SAMPLE_ARTICLE = """\
---
type: article
visibility: PUBLIC
url: https://example.com/article
tags: [tech]
---

Check out this article about testing.
"""

SAMPLE_SCHEDULED = """\
---
type: text
target_date: {date}
target_time: {time}
visibility: PUBLIC
---

Scheduled post content.
"""

OVERLENGTH_POST = """\
---
type: text
visibility: PUBLIC
---

""" + "x" * 3001


class PipelineTestBase(TestCase):
    """Base class that sets up a temporary pipeline directory."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        for stage in server.STAGES:
            (self.tmpdir / stage).mkdir()
        (self.tmpdir / "pages").mkdir()
        self._orig_base = server.BASE
        self._orig_pages = server.PAGES_DIR
        server.BASE = self.tmpdir
        server.PAGES_DIR = self.tmpdir / "pages"

    def tearDown(self):
        server.BASE = self._orig_base
        server.PAGES_DIR = self._orig_pages
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_post(self, stage, filename, content):
        path = self.tmpdir / stage / filename
        path.write_text(content, encoding="utf-8")
        return path


class TestParsePost(PipelineTestBase):

    def test_parse_basic_post(self):
        self.write_post("draft", "2026-01-01-test.md", SAMPLE_POST)
        post = server.parse_post(self.tmpdir / "draft" / "2026-01-01-test.md")
        self.assertEqual(post["type"], "text")
        self.assertEqual(post["visibility"], "PUBLIC")
        self.assertEqual(post["tags"], ["test", "demo"])
        self.assertEqual(post["filename"], "2026-01-01-test.md")
        self.assertEqual(post["stage"], "draft")
        self.assertIn("This is a test post body.", post["body"])
        self.assertEqual(post["char_count"], len(post["body"]))

    def test_parse_article_post(self):
        self.write_post("approved", "2026-01-01-article.md", SAMPLE_ARTICLE)
        post = server.parse_post(self.tmpdir / "approved" / "2026-01-01-article.md")
        self.assertEqual(post["type"], "article")
        self.assertEqual(post["url"], "https://example.com/article")

    def test_parse_no_frontmatter(self):
        self.write_post("draft", "plain.md", "Just plain text, no frontmatter.")
        post = server.parse_post(self.tmpdir / "draft" / "plain.md")
        self.assertEqual(post["body"], "Just plain text, no frontmatter.")
        self.assertNotIn("type", post)

    def test_parse_scheduled_with_time(self):
        content = SAMPLE_SCHEDULED.format(date="2026-07-01", time="14:30")
        self.write_post("scheduled", "2026-07-01-test.md", content)
        post = server.parse_post(self.tmpdir / "scheduled" / "2026-07-01-test.md")
        self.assertEqual(post["target_date"], "2026-07-01")
        self.assertEqual(post["target_time"], "14:30")


class TestListPosts(PipelineTestBase):

    def test_list_empty_stage(self):
        self.assertEqual(server.list_posts("draft"), [])

    def test_list_posts_returns_all(self):
        self.write_post("draft", "a.md", SAMPLE_POST)
        self.write_post("draft", "b.md", SAMPLE_POST)
        posts = server.list_posts("draft")
        self.assertEqual(len(posts), 2)

    def test_list_nonexistent_stage(self):
        self.assertEqual(server.list_posts("nonexistent"), [])

    def test_completed_limited_to_max(self):
        for i in range(15):
            content = f"---\ntype: text\nposted_date: 2026-01-{i+1:02d} 09:00\n---\n\nPost {i}\n"
            self.write_post("completed", f"2026-01-{i+1:02d}-post{i}.md", content)
        posts = server.list_posts("completed")
        self.assertEqual(len(posts), server.MAX_COMPLETED_DISPLAY)

    def test_completed_sorted_by_posted_date_desc(self):
        self.write_post("completed", "old.md", "---\ntype: text\nposted_date: 2026-01-01 09:00\n---\n\nOld\n")
        self.write_post("completed", "new.md", "---\ntype: text\nposted_date: 2026-06-15 09:00\n---\n\nNew\n")
        posts = server.list_posts("completed")
        self.assertEqual(posts[0]["filename"], "new.md")
        self.assertEqual(posts[1]["filename"], "old.md")


class TestBuildFileContent(PipelineTestBase):

    def test_build_text_post(self):
        meta = {"type": "text", "visibility": "PUBLIC"}
        content = server.build_file_content(meta, "Hello world")
        self.assertIn("type: text", content)
        self.assertIn("visibility: PUBLIC", content)
        self.assertIn("Hello world", content)

    def test_build_with_target_time(self):
        meta = {"type": "text", "target_date": "2026-07-01", "target_time": "14:30", "visibility": "PUBLIC"}
        content = server.build_file_content(meta, "Timed post")
        self.assertIn("target_time: 14:30", content)

    def test_build_with_tags_list(self):
        meta = {"type": "text", "visibility": "PUBLIC", "tags": ["a", "b", "c"]}
        content = server.build_file_content(meta, "Tagged")
        self.assertIn("tags: [a, b, c]", content)

    def test_build_with_tags_string(self):
        meta = {"type": "text", "visibility": "PUBLIC", "tags": "single"}
        content = server.build_file_content(meta, "Tagged")
        self.assertIn("tags: single", content)

    def test_build_roundtrip(self):
        meta = {"type": "article", "target_date": "2026-07-01", "target_time": "10:00",
                "visibility": "CONNECTIONS", "url": "https://example.com", "tags": ["x"]}
        body = "Round trip content"
        content = server.build_file_content(meta, body)
        path = self.tmpdir / "draft" / "test.md"
        path.write_text(content, encoding="utf-8")
        parsed = server.parse_post(path)
        self.assertEqual(parsed["type"], "article")
        self.assertEqual(parsed["target_date"], "2026-07-01")
        self.assertEqual(parsed["target_time"], "10:00")
        self.assertEqual(parsed["visibility"], "CONNECTIONS")
        self.assertEqual(parsed["url"], "https://example.com")
        self.assertEqual(parsed["body"], body)


class TestGetDuePosts(PipelineTestBase):

    def test_no_scheduled_posts(self):
        self.assertEqual(server.get_due_posts(), [])

    def test_future_post_not_due(self):
        future = (date.today() + timedelta(days=7)).isoformat()
        content = SAMPLE_SCHEDULED.format(date=future, time="09:00")
        self.write_post("scheduled", f"{future}-future.md", content)
        self.assertEqual(server.get_due_posts(), [])

    def test_overdue_post(self):
        past = (date.today() - timedelta(days=2)).isoformat()
        content = SAMPLE_SCHEDULED.format(date=past, time="09:00")
        self.write_post("scheduled", f"{past}-overdue.md", content)
        due = server.get_due_posts()
        self.assertEqual(len(due), 1)
        self.assertTrue(due[0]["overdue"])

    def test_today_post_past_time(self):
        today = date.today().isoformat()
        content = SAMPLE_SCHEDULED.format(date=today, time="00:00")
        self.write_post("scheduled", f"{today}-now.md", content)
        due = server.get_due_posts()
        self.assertEqual(len(due), 1)
        self.assertFalse(due[0]["overdue"])

    def test_today_post_future_time(self):
        today = date.today().isoformat()
        content = SAMPLE_SCHEDULED.format(date=today, time="23:59")
        self.write_post("scheduled", f"{today}-later.md", content)
        due = server.get_due_posts()
        # Should not be due unless it's actually 23:59
        now = datetime.now()
        if now.hour < 23 or (now.hour == 23 and now.minute < 59):
            self.assertEqual(len(due), 0)

    def test_no_target_date_skipped(self):
        self.write_post("scheduled", "no-date.md", SAMPLE_POST)
        self.assertEqual(server.get_due_posts(), [])


class TestMarkPosted(PipelineTestBase):

    def test_mark_posted_moves_to_completed(self):
        content = SAMPLE_SCHEDULED.format(date="2026-06-20", time="09:00")
        self.write_post("scheduled", "2026-06-20-test.md", content)
        result = server.mark_posted("2026-06-20-test.md")
        self.assertTrue(result["ok"])
        self.assertFalse((self.tmpdir / "scheduled" / "2026-06-20-test.md").exists())
        self.assertTrue((self.tmpdir / "completed" / "2026-06-20-test.md").exists())

    def test_mark_posted_adds_posted_date(self):
        content = SAMPLE_SCHEDULED.format(date="2026-06-20", time="09:00")
        self.write_post("scheduled", "2026-06-20-test.md", content)
        server.mark_posted("2026-06-20-test.md", "2026-06-20 10:30")
        text = (self.tmpdir / "completed" / "2026-06-20-test.md").read_text(encoding="utf-8")
        self.assertIn("posted_date: 2026-06-20 10:30", text)

    def test_mark_posted_updates_existing_posted_date(self):
        content = "---\ntype: text\ntarget_date: 2026-06-20\nposted_date: old\n---\n\nContent\n"
        self.write_post("scheduled", "test.md", content)
        server.mark_posted("test.md", "2026-06-20 11:00")
        text = (self.tmpdir / "completed" / "test.md").read_text(encoding="utf-8")
        self.assertIn("posted_date: 2026-06-20 11:00", text)
        self.assertNotIn("old", text)

    def test_mark_posted_file_not_found(self):
        result = server.mark_posted("nonexistent.md")
        self.assertIn("error", result)


class TestUpdateIndex(PipelineTestBase):

    def test_creates_posting_plan(self):
        self.write_post("draft", "2026-01-01-test.md", SAMPLE_POST)
        server.update_index()
        plan = (self.tmpdir / "posting-plan.md").read_text(encoding="utf-8")
        self.assertIn("# LinkedIn Posting Plan", plan)
        self.assertIn("2026-01-01-test.md", plan)

    def test_empty_stages_show_none(self):
        server.update_index()
        plan = (self.tmpdir / "posting-plan.md").read_text(encoding="utf-8")
        self.assertIn("_(none)_", plan)


class TestAPIEndpoints(PipelineTestBase):
    """Integration tests using a real HTTP server on a random port."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir_class = Path(tempfile.mkdtemp())
        for stage in server.STAGES:
            (cls.tmpdir_class / stage).mkdir()
        (cls.tmpdir_class / "pages").mkdir()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir_class, ignore_errors=True)

    def setUp(self):
        super().setUp()
        server.BASE = self.tmpdir
        server.PAGES_DIR = self.tmpdir / "pages"
        self.httpd = server.http.server.HTTPServer(("127.0.0.1", 0), server.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        super().tearDown()

    def api(self, method, path, data=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
        try:
            resp = urllib.request.urlopen(req)
            return json.loads(resp.read()), resp.status
        except urllib.error.HTTPError as e:
            return json.loads(e.read()), e.code

    def test_get_posts_empty(self):
        data, status = self.api("GET", "/api/posts")
        self.assertEqual(status, 200)
        for stage in server.STAGES:
            self.assertEqual(data[stage], [])

    def test_create_post(self):
        data, status = self.api("POST", "/api/create", {
            "slug": "my-test", "type": "text", "visibility": "PUBLIC", "body": "Hello"
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertIn("my-test", data["filename"])
        self.assertTrue((self.tmpdir / "draft" / data["filename"]).exists())

    def test_create_post_no_slug(self):
        data, status = self.api("POST", "/api/create", {"body": "No slug"})
        self.assertEqual(status, 400)
        self.assertIn("error", data)

    def test_create_duplicate_slug(self):
        self.api("POST", "/api/create", {"slug": "dup", "body": "First"})
        data, status = self.api("POST", "/api/create", {"slug": "dup", "body": "Second"})
        self.assertEqual(status, 400)

    def test_move_post(self):
        r, _ = self.api("POST", "/api/create", {"slug": "moveme", "body": "Move"})
        data, status = self.api("POST", "/api/move", {
            "from": "draft", "to": "approved", "filename": r["filename"]
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertTrue((self.tmpdir / "approved" / r["filename"]).exists())

    def test_move_to_scheduled_blocks_overlength(self):
        path = self.tmpdir / "approved" / "big.md"
        path.write_text(OVERLENGTH_POST, encoding="utf-8")
        data, status = self.api("POST", "/api/move", {
            "from": "approved", "to": "scheduled", "filename": "big.md"
        })
        self.assertEqual(status, 400)
        self.assertIn("3000", data["error"])

    def test_schedule_post(self):
        r, _ = self.api("POST", "/api/create", {"slug": "sched", "body": "Schedule me"})
        self.api("POST", "/api/move", {"from": "draft", "to": "approved", "filename": r["filename"]})
        data, status = self.api("POST", "/api/schedule", {
            "filename": r["filename"], "target_date": "2026-08-01", "target_time": "14:00"
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertIn("2026-08-01", data["filename"])
        scheduled_file = self.tmpdir / "scheduled" / data["filename"]
        self.assertTrue(scheduled_file.exists())
        text = scheduled_file.read_text(encoding="utf-8")
        self.assertIn("target_date: 2026-08-01", text)
        self.assertIn("target_time: 14:00", text)

    def test_schedule_blocks_overlength(self):
        path = self.tmpdir / "approved" / "big.md"
        path.write_text(OVERLENGTH_POST, encoding="utf-8")
        data, status = self.api("POST", "/api/schedule", {
            "filename": "big.md", "target_date": "2026-08-01"
        })
        self.assertEqual(status, 400)
        self.assertIn("3000", data["error"])

    def test_schedule_default_time(self):
        r, _ = self.api("POST", "/api/create", {"slug": "notime", "body": "No time given"})
        self.api("POST", "/api/move", {"from": "draft", "to": "approved", "filename": r["filename"]})
        data, _ = self.api("POST", "/api/schedule", {
            "filename": r["filename"], "target_date": "2026-08-01"
        })
        text = (self.tmpdir / "scheduled" / data["filename"]).read_text(encoding="utf-8")
        self.assertIn("target_time: 09:00", text)

    def test_edit_post(self):
        r, _ = self.api("POST", "/api/create", {"slug": "editable", "body": "Original"})
        data, status = self.api("POST", "/api/edit", {
            "stage": "draft", "filename": r["filename"],
            "type": "text", "visibility": "PUBLIC", "body": "Updated content"
        })
        self.assertEqual(status, 200)
        text = (self.tmpdir / "draft" / r["filename"]).read_text(encoding="utf-8")
        self.assertIn("Updated content", text)

    def test_edit_approved_reverts_to_draft(self):
        r, _ = self.api("POST", "/api/create", {"slug": "revert", "body": "Will be reverted"})
        self.api("POST", "/api/move", {"from": "draft", "to": "approved", "filename": r["filename"]})
        data, status = self.api("POST", "/api/edit", {
            "stage": "approved", "filename": r["filename"],
            "type": "text", "visibility": "PUBLIC", "body": "Edited while approved"
        })
        self.assertEqual(status, 200)
        self.assertTrue(data.get("reverted"))
        self.assertFalse((self.tmpdir / "approved" / r["filename"]).exists())
        self.assertTrue((self.tmpdir / "draft" / r["filename"]).exists())

    def test_edit_scheduled_reverts_to_draft(self):
        content = SAMPLE_SCHEDULED.format(date="2026-08-01", time="09:00")
        self.write_post("scheduled", "2026-08-01-sched.md", content)
        data, status = self.api("POST", "/api/edit", {
            "stage": "scheduled", "filename": "2026-08-01-sched.md",
            "type": "text", "visibility": "PUBLIC", "body": "Edited scheduled post"
        })
        self.assertEqual(status, 200)
        self.assertTrue(data.get("reverted"))
        self.assertFalse((self.tmpdir / "scheduled" / "2026-08-01-sched.md").exists())
        self.assertTrue((self.tmpdir / "draft" / "2026-08-01-sched.md").exists())

    def test_delete_post(self):
        r, _ = self.api("POST", "/api/create", {"slug": "deleteme", "body": "Delete"})
        data, status = self.api("POST", "/api/delete", {
            "stage": "draft", "filename": r["filename"]
        })
        self.assertEqual(status, 200)
        self.assertFalse((self.tmpdir / "draft" / r["filename"]).exists())

    def test_delete_nonexistent(self):
        data, status = self.api("POST", "/api/delete", {
            "stage": "draft", "filename": "ghost.md"
        })
        self.assertEqual(status, 400)

    def test_mark_posted_api(self):
        content = SAMPLE_SCHEDULED.format(date="2026-06-20", time="09:00")
        self.write_post("scheduled", "2026-06-20-mark.md", content)
        data, status = self.api("POST", "/api/mark-posted", {"filename": "2026-06-20-mark.md"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertTrue((self.tmpdir / "completed" / "2026-06-20-mark.md").exists())

    def test_mark_posted_no_filename(self):
        data, status = self.api("POST", "/api/mark-posted", {})
        self.assertEqual(status, 400)

    def test_get_due(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        content = SAMPLE_SCHEDULED.format(date=past, time="09:00")
        self.write_post("scheduled", f"{past}-due.md", content)
        data, status = self.api("GET", "/api/due")
        self.assertEqual(status, 200)
        self.assertEqual(len(data), 1)

    def test_get_schedule_view(self):
        content = SAMPLE_SCHEDULED.format(date="2026-08-01", time="09:00")
        self.write_post("scheduled", "2026-08-01-view.md", content)
        data, status = self.api("GET", "/api/schedule-view")
        self.assertEqual(status, 200)
        self.assertIn("scheduled", data)
        self.assertIn("completed", data)
        self.assertIn("today", data)
        self.assertEqual(len(data["scheduled"]), 1)

    def test_move_invalid_stage(self):
        data, status = self.api("POST", "/api/move", {
            "from": "draft", "to": "invalid", "filename": "x.md"
        })
        self.assertEqual(status, 400)

    def test_404_unknown_route(self):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/nonexistent")
            urllib.request.urlopen(req)
            self.fail("Should have raised HTTPError")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


if __name__ == "__main__":
    main()
