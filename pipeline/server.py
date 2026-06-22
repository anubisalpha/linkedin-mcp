"""LinkedIn Pipeline — Local posting dashboard.

Run:  python pipeline/server.py
Open: http://localhost:8420
"""

import http.server
import json
import os
import re
import shutil
import urllib.parse
from datetime import date, datetime
from pathlib import Path

PORT = int(os.environ.get("PORT", 8420))
BASE = Path(__file__).parent
STAGES = ["draft", "approved", "scheduled", "completed"]
MAX_POST_LENGTH = 3000

def parse_post(filepath):
    text = filepath.read_text(encoding="utf-8")
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                m = re.match(r"^(\w[\w_]*)\s*:\s*(.+)$", line)
                if m:
                    key, val = m.group(1), m.group(2).strip()
                    if val.startswith("[") and val.endswith("]"):
                        val = [v.strip().strip("'\"") for v in val[1:-1].split(",")]
                    meta[key] = val
            body = parts[2].strip()
    meta["filename"] = filepath.name
    meta["body"] = body
    meta["stage"] = filepath.parent.name
    meta["char_count"] = len(body)
    return meta

def get_due_posts():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    due = []
    for post in list_posts("scheduled"):
        td = post.get("target_date", "")
        tt = post.get("target_time", "09:00")
        if not td:
            continue
        if td < today:
            post["overdue"] = True
            due.append(post)
        elif td == today and current_time >= tt:
            post["overdue"] = False
            due.append(post)
    return due

def mark_posted(filename, posted_date=None):
    filepath = BASE / "scheduled" / filename
    if not filepath.exists():
        return {"error": "File not found in scheduled/"}
    if not posted_date:
        posted_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = filepath.read_text(encoding="utf-8")
    if "posted_date:" in text:
        text = re.sub(r"posted_date:\s*.+", f"posted_date: {posted_date}", text)
    elif text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = f"---\n{parts[1].strip()}\nposted_date: {posted_date}\n---{parts[2]}"
    filepath.write_text(text, encoding="utf-8")
    dst = BASE / "completed" / filename
    shutil.move(str(filepath), str(dst))
    update_index()
    return {"ok": True}

def build_file_content(meta, body):
    lines = ["---"]
    if meta.get("type"):
        lines.append(f"type: {meta['type']}")
    if meta.get("target_date"):
        lines.append(f"target_date: {meta['target_date']}")
    if meta.get("target_time"):
        lines.append(f"target_time: {meta['target_time']}")
    if meta.get("visibility"):
        lines.append(f"visibility: {meta['visibility']}")
    if meta.get("url"):
        lines.append(f"url: {meta['url']}")
    if meta.get("image"):
        lines.append(f"image: {meta['image']}")
    if meta.get("tags"):
        if isinstance(meta["tags"], list):
            lines.append(f"tags: [{', '.join(meta['tags'])}]")
        else:
            lines.append(f"tags: {meta['tags']}")
    if meta.get("posted_date"):
        lines.append(f"posted_date: {meta['posted_date']}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    lines.append("")
    return "\n".join(lines)

MAX_COMPLETED_DISPLAY = 12

def list_posts(stage):
    folder = BASE / stage
    if not folder.exists():
        return []
    posts = []
    for f in sorted(folder.glob("*.md")):
        posts.append(parse_post(f))
    if stage == "completed":
        posts.sort(key=lambda p: p.get("posted_date", ""), reverse=True)
        posts = posts[:MAX_COMPLETED_DISPLAY]
    return posts

def update_index():
    lines = [
        "# LinkedIn Posting Plan\n",
        "Target: 1-2 posts per week | Daily check: 9:00 AM\n",
        "## Pipeline\n",
    ]
    labels = {"draft": "Draft", "approved": "Approved", "scheduled": "Scheduled", "completed": "Completed"}
    for stage in STAGES:
        lines.append(f"### {labels[stage]}")
        posts = list_posts(stage)
        if posts:
            for p in posts:
                target = f" (target: {p['target_date']})" if p.get("target_date") else ""
                desc = p.get("body", "").split("\n")[0][:80]
                lines.append(f"- [{p['filename']}]({stage}/{p['filename']}) — {desc}{target}")
        else:
            lines.append("_(none)_")
        lines.append("")
    (BASE / "posting-plan.md").write_text("\n".join(lines), encoding="utf-8")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
}
PAGES_DIR = BASE / "pages"

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def serve_file(self, filepath):
        if not filepath.exists():
            self.send_response(404)
            self.end_headers()
            return
        ext = filepath.suffix.lower()
        ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(data))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?")[0])
        if path == "/" or path == "/index.html":
            self.serve_file(PAGES_DIR / "index.html")
        elif path.startswith("/pages/"):
            safe = Path(path.lstrip("/"))
            target = BASE / safe
            if target.resolve().is_relative_to(PAGES_DIR.resolve()) and target.is_file():
                self.serve_file(target)
            else:
                self.send_response(404)
                self.end_headers()
        elif path == "/api/posts":
            result = {}
            for stage in STAGES:
                result[stage] = list_posts(stage)
            self.send_json(result)
        elif path == "/api/due":
            self.send_json(get_due_posts())
        elif path == "/api/schedule-view":
            scheduled = list_posts("scheduled")
            completed = list_posts("completed")
            self.send_json({"scheduled": scheduled, "completed": completed, "today": date.today().isoformat()})
        elif path == "/schedule" or path == "/schedule.html":
            self.serve_file(PAGES_DIR / "schedule.html")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/move":
            data = self.read_body()
            src = BASE / data["from"] / data["filename"]
            dst_dir = BASE / data["to"]
            if not src.exists() or data["from"] not in STAGES or data["to"] not in STAGES:
                self.send_json({"error": "Invalid stage or file not found"}, 400)
                return
            if data["to"] == "scheduled":
                post = parse_post(src)
                if post["char_count"] > MAX_POST_LENGTH:
                    self.send_json({"error": f"Post is {post['char_count']} characters — exceeds the {MAX_POST_LENGTH} character limit. Edit the post before scheduling."}, 400)
                    return
            dst = dst_dir / data["filename"]
            shutil.move(str(src), str(dst))
            update_index()
            self.send_json({"ok": True})

        elif self.path == "/api/schedule":
            data = self.read_body()
            filename = data["filename"]
            target_date = data["target_date"]
            target_time = data.get("target_time", "09:00")
            filepath = BASE / "approved" / filename
            if not filepath.exists():
                self.send_json({"error": "File not found in approved/"}, 400)
                return
            post = parse_post(filepath)
            if post["char_count"] > MAX_POST_LENGTH:
                self.send_json({"error": f"Post is {post['char_count']} characters — exceeds the {MAX_POST_LENGTH} character limit. Edit the post before scheduling."}, 400)
                return
            text = filepath.read_text(encoding="utf-8")
            if "target_date:" in text:
                text = re.sub(r"target_date:\s*.+", f"target_date: {target_date}", text)
            elif text.startswith("---"):
                text = text.replace("---\n", f"---\ntarget_date: {target_date}\n", 1)
            if "target_time:" in text:
                text = re.sub(r"target_time:\s*.+", f"target_time: {target_time}", text)
            elif text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    text = f"---\n{parts[1].strip()}\ntarget_time: {target_time}\n---{parts[2]}"
            new_name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", filename)
            new_name = f"{target_date}-{new_name}"
            filepath.write_text(text, encoding="utf-8")
            dst = BASE / "scheduled" / new_name
            shutil.move(str(filepath), str(dst))
            update_index()
            self.send_json({"ok": True, "filename": new_name})

        elif self.path == "/api/create":
            data = self.read_body()
            slug = data.get("slug", "").strip()
            if not slug:
                self.send_json({"error": "Slug is required"}, 400)
                return
            slug = re.sub(r"[^a-z0-9-]", "-", slug.lower()).strip("-")
            today = data.get("date", "")
            if not today:
                from datetime import date
                today = date.today().isoformat()
            filename = f"{today}-{slug}.md"
            filepath = BASE / "draft" / filename
            if filepath.exists():
                self.send_json({"error": "A draft with that name already exists"}, 400)
                return
            meta = {
                "type": data.get("type", "text"),
                "visibility": data.get("visibility", "PUBLIC"),
            }
            if data.get("target_date"):
                meta["target_date"] = data["target_date"]
            if data.get("target_time"):
                meta["target_time"] = data["target_time"]
            if data.get("url"):
                meta["url"] = data["url"]
            if data.get("tags"):
                meta["tags"] = data["tags"]
            body = data.get("body", "")
            content = build_file_content(meta, body)
            filepath.write_text(content, encoding="utf-8")
            update_index()
            self.send_json({"ok": True, "filename": filename})

        elif self.path == "/api/edit":
            data = self.read_body()
            stage = data.get("stage", "")
            filename = data.get("filename", "")
            if stage not in STAGES or not filename:
                self.send_json({"error": "Invalid stage or filename"}, 400)
                return
            filepath = BASE / stage / filename
            if not filepath.exists():
                self.send_json({"error": "File not found"}, 400)
                return
            meta = {
                "type": data.get("type", "text"),
                "visibility": data.get("visibility", "PUBLIC"),
            }
            if data.get("target_date"):
                meta["target_date"] = data["target_date"]
            if data.get("target_time"):
                meta["target_time"] = data["target_time"]
            if data.get("url"):
                meta["url"] = data["url"]
            if data.get("image"):
                meta["image"] = data["image"]
            if data.get("tags"):
                meta["tags"] = data["tags"]
            body = data.get("body", "")
            content = build_file_content(meta, body)
            final_name = data.get("new_filename", "").strip() or filename
            filepath.write_text(content, encoding="utf-8")
            if final_name != filename:
                shutil.move(str(filepath), str(BASE / stage / final_name))
                filepath = BASE / stage / final_name
            if stage in ("approved", "scheduled"):
                dst = BASE / "draft" / final_name
                shutil.move(str(filepath), str(dst))
                stage = "draft"
            update_index()
            self.send_json({"ok": True, "reverted": stage == "draft"})

        elif self.path == "/api/mark-posted":
            data = self.read_body()
            filename = data.get("filename", "")
            if not filename:
                self.send_json({"error": "Filename required"}, 400)
                return
            result = mark_posted(filename)
            status = 200 if "ok" in result else 400
            self.send_json(result, status)

        elif self.path == "/api/delete":
            data = self.read_body()
            stage = data.get("stage", "")
            filename = data.get("filename", "")
            if stage not in STAGES or not filename:
                self.send_json({"error": "Invalid stage or filename"}, 400)
                return
            filepath = BASE / stage / filename
            if not filepath.exists():
                self.send_json({"error": "File not found"}, 400)
                return
            filepath.unlink()
            update_index()
            self.send_json({"ok": True})

        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    for stage in STAGES:
        (BASE / stage).mkdir(exist_ok=True)
    PAGES_DIR.mkdir(exist_ok=True)
    print(f"LinkedIn Pipeline running at http://localhost:{PORT}")
    print(f"Serving pages from {PAGES_DIR}")
    http.server.HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
