from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from .models import PostResult, Profile


@dataclass
class LinkPreview:
    url: str
    title: str = ""
    description: str = ""
    image: str = ""
    site_name: str = ""

    def summary(self) -> str:
        lines = [f"Link preview for: {self.url}", ""]
        if self.site_name:
            lines.append(f"Site: {self.site_name}")
        if self.title:
            lines.append(f"Title: {self.title}")
        if self.description:
            lines.append(f"Description: {self.description}")
        if self.image:
            lines.append(f"Image: {self.image}")
        if not self.title and not self.description:
            lines.append("No Open Graph metadata found — LinkedIn may show a plain URL card.")
        return "\n".join(lines)

DEFAULT_APPROVAL_STAMP = "\n\n—\nAI-drafted · Human-approved · Posted via LinkedIn MCP"

API_BASE = "https://api.linkedin.com/v2"
REST_BASE = "https://api.linkedin.com/rest"
USERINFO_URL = f"{API_BASE}/userinfo"
UGC_POSTS_URL = f"{API_BASE}/ugcPosts"
ASSETS_URL = f"{API_BASE}/assets"
POSTS_URL = f"{REST_BASE}/posts"
DOCUMENTS_URL = f"{REST_BASE}/documents"
VIDEOS_URL = f"{REST_BASE}/videos"

RESTLI_HEADER = {"X-Restli-Protocol-Version": "2.0.0"}
LINKEDIN_VERSION = "202405"


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        **RESTLI_HEADER,
    }


def _rest_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        **RESTLI_HEADER,
    }


def get_profile(access_token: str) -> Profile:
    """Fetch the authenticated member's profile from the userinfo endpoint."""
    resp = httpx.get(USERINFO_URL, headers=_headers(access_token))
    resp.raise_for_status()
    data = resp.json()
    return Profile(
        sub=data.get("sub", ""),
        name=data.get("name", ""),
        given_name=data.get("given_name", ""),
        family_name=data.get("family_name", ""),
        picture=data.get("picture", ""),
        locale=data.get("locale", ""),
        email=data.get("email", ""),
        email_verified=data.get("email_verified", False),
    )


def _get_approval_stamp() -> str:
    """Return the approval stamp to append to posts.

    Configurable via LINKEDIN_MCP_APPROVAL_STAMP env var.
    Set to empty string to disable.
    """
    stamp = os.environ.get("LINKEDIN_MCP_APPROVAL_STAMP")
    if stamp is not None:
        return stamp if stamp else ""
    return DEFAULT_APPROVAL_STAMP


def _stamp_text(text: str) -> str:
    """Append the approval stamp to post text."""
    stamp = _get_approval_stamp()
    if stamp:
        return text + stamp
    return text


def _build_ugc_post(
    person_urn: str,
    text: str,
    visibility: str = "PUBLIC",
    media_category: str = "NONE",
    media: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    share_content: dict[str, object] = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": media_category,
    }
    if media:
        share_content["media"] = media
    post: dict[str, object] = {
        "author": f"urn:li:person:{person_urn}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": share_content,
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility,
        },
    }
    return post


def create_text_post(
    access_token: str,
    person_urn: str,
    text: str,
    visibility: str = "PUBLIC",
) -> PostResult:
    """Create a text-only post on LinkedIn."""
    body = _build_ugc_post(person_urn, _stamp_text(text), visibility)
    resp = httpx.post(UGC_POSTS_URL, json=body, headers=_headers(access_token))
    resp.raise_for_status()
    urn = resp.headers.get("X-RestLi-Id", "")
    return PostResult(urn=urn, status="created", message=f"Post published: {urn}")


def create_article_post(
    access_token: str,
    person_urn: str,
    text: str,
    url: str,
    title: str = "",
    description: str = "",
    visibility: str = "PUBLIC",
) -> PostResult:
    """Share a URL/article with commentary on LinkedIn."""
    media_item: dict[str, object] = {"status": "READY", "originalUrl": url}
    if title:
        media_item["title"] = {"text": title}
    if description:
        media_item["description"] = {"text": description}

    body = _build_ugc_post(
        person_urn, _stamp_text(text), visibility, media_category="ARTICLE", media=[media_item]
    )
    resp = httpx.post(UGC_POSTS_URL, json=body, headers=_headers(access_token))
    resp.raise_for_status()
    urn = resp.headers.get("X-RestLi-Id", "")
    return PostResult(urn=urn, status="created", message=f"Article shared: {urn}")


def _register_image_upload(access_token: str, person_urn: str) -> tuple[str, str]:
    """Register an image for upload. Returns (upload_url, asset_urn)."""
    body = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": f"urn:li:person:{person_urn}",
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }
    resp = httpx.post(
        f"{ASSETS_URL}?action=registerUpload",
        json=body,
        headers=_headers(access_token),
    )
    resp.raise_for_status()
    data = resp.json()["value"]
    upload_url = data["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]["uploadUrl"]
    asset_urn = data["asset"]
    return upload_url, asset_urn


def _upload_image_binary(access_token: str, upload_url: str, image_path: str) -> None:
    """Upload the image binary to LinkedIn's upload URL."""
    image_data = Path(image_path).read_bytes()
    resp = httpx.put(
        upload_url,
        content=image_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()


def create_image_post(
    access_token: str,
    person_urn: str,
    text: str,
    image_path: str,
    title: str = "",
    description: str = "",
    visibility: str = "PUBLIC",
) -> PostResult:
    """Upload an image and create a post with it on LinkedIn."""
    upload_url, asset_urn = _register_image_upload(access_token, person_urn)
    _upload_image_binary(access_token, upload_url, image_path)

    media_item: dict[str, object] = {"status": "READY", "media": asset_urn}
    if title:
        media_item["title"] = {"text": title}
    if description:
        media_item["description"] = {"text": description}

    body = _build_ugc_post(
        person_urn, _stamp_text(text), visibility, media_category="IMAGE", media=[media_item]
    )
    resp = httpx.post(UGC_POSTS_URL, json=body, headers=_headers(access_token))
    resp.raise_for_status()
    urn = resp.headers.get("X-RestLi-Id", "")
    return PostResult(urn=urn, status="created", message=f"Image post published: {urn}")


def delete_post(access_token: str, post_urn: str) -> PostResult:
    """Delete a post by its URN."""
    encoded_urn = post_urn.replace(":", "%3A").replace("(", "%28").replace(")", "%29")
    resp = httpx.delete(
        f"{UGC_POSTS_URL}/{encoded_urn}",
        headers=_headers(access_token),
    )
    resp.raise_for_status()
    return PostResult(urn=post_urn, status="deleted", message=f"Post deleted: {post_urn}")


POLL_DURATION_MAP = {
    "1_DAY": "ONE_DAY",
    "3_DAYS": "THREE_DAYS",
    "7_DAYS": "SEVEN_DAYS",
    "14_DAYS": "FOURTEEN_DAYS",
}


def create_poll_post(
    access_token: str,
    person_urn: str,
    text: str,
    question: str,
    options: list[str],
    duration: str = "3_DAYS",
    visibility: str = "PUBLIC",
) -> PostResult:
    """Create a poll post on LinkedIn using the Posts API."""
    api_duration = POLL_DURATION_MAP.get(duration, "THREE_DAYS")
    poll_options = [{"text": opt} for opt in options]

    vis_value = "PUBLIC" if visibility == "PUBLIC" else "CONNECTIONS"
    body: dict[str, object] = {
        "author": f"urn:li:person:{person_urn}",
        "commentary": _stamp_text(text),
        "visibility": vis_value,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "content": {
            "poll": {
                "question": question,
                "options": poll_options,
                "settings": {"duration": api_duration},
            }
        },
    }
    resp = httpx.post(
        POSTS_URL,
        json=body,
        headers=_rest_headers(access_token),
    )
    resp.raise_for_status()
    urn = resp.headers.get("X-RestLi-Id", "")
    return PostResult(urn=urn, status="created", message=f"Poll published: {urn}")


def _register_document_upload(access_token: str, person_urn: str) -> tuple[str, str]:
    """Register a document for upload. Returns (upload_url, document_urn)."""
    body = {
        "initializeUploadRequest": {
            "owner": f"urn:li:person:{person_urn}",
        }
    }
    resp = httpx.post(
        f"{DOCUMENTS_URL}?action=initializeUpload",
        json=body,
        headers=_rest_headers(access_token),
    )
    resp.raise_for_status()
    data = resp.json()["value"]
    upload_url: str = data["uploadUrl"]
    document_urn: str = data["document"]
    return upload_url, document_urn


def _upload_document_binary(access_token: str, upload_url: str, file_path: str) -> None:
    """Upload the document binary to LinkedIn's upload URL."""
    file_data = Path(file_path).read_bytes()
    resp = httpx.put(
        upload_url,
        content=file_data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream",
        },
        timeout=120,
    )
    resp.raise_for_status()


def create_document_post(
    access_token: str,
    person_urn: str,
    text: str,
    file_path: str,
    title: str = "",
    visibility: str = "PUBLIC",
) -> PostResult:
    """Upload a document (PDF, etc.) and create a post with it on LinkedIn."""
    upload_url, document_urn = _register_document_upload(access_token, person_urn)
    _upload_document_binary(access_token, upload_url, file_path)

    vis_value = "PUBLIC" if visibility == "PUBLIC" else "CONNECTIONS"
    doc_content: dict[str, object] = {"media": document_urn}
    if title:
        doc_content["title"] = title

    body: dict[str, object] = {
        "author": f"urn:li:person:{person_urn}",
        "commentary": _stamp_text(text),
        "visibility": vis_value,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "content": {"article": doc_content},
    }
    resp = httpx.post(
        POSTS_URL,
        json=body,
        headers=_rest_headers(access_token),
    )
    resp.raise_for_status()
    urn = resp.headers.get("X-RestLi-Id", "")
    return PostResult(urn=urn, status="created", message=f"Document post published: {urn}")


def _register_video_upload(
    access_token: str, person_urn: str, file_size: int
) -> tuple[str, str]:
    """Register a video for upload. Returns (upload_url, video_urn)."""
    body = {
        "initializeUploadRequest": {
            "owner": f"urn:li:person:{person_urn}",
            "fileSizeBytes": file_size,
            "uploadCausalItyEnabled": True,
        }
    }
    resp = httpx.post(
        f"{VIDEOS_URL}?action=initializeUpload",
        json=body,
        headers=_rest_headers(access_token),
    )
    resp.raise_for_status()
    data = resp.json()["value"]
    upload_url: str = data["uploadInstructions"][0]["uploadUrl"]
    video_urn: str = data["video"]
    return upload_url, video_urn


def _upload_video_binary(access_token: str, upload_url: str, video_path: str) -> None:
    """Upload the video binary to LinkedIn's upload URL."""
    video_data = Path(video_path).read_bytes()
    resp = httpx.put(
        upload_url,
        content=video_data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream",
        },
        timeout=600,
    )
    resp.raise_for_status()


def create_video_post(
    access_token: str,
    person_urn: str,
    text: str,
    video_path: str,
    title: str = "",
    visibility: str = "PUBLIC",
) -> PostResult:
    """Upload a video and create a post with it on LinkedIn."""
    file_size = Path(video_path).stat().st_size
    upload_url, video_urn = _register_video_upload(access_token, person_urn, file_size)
    _upload_video_binary(access_token, upload_url, video_path)

    vis_value = "PUBLIC" if visibility == "PUBLIC" else "CONNECTIONS"
    video_content: dict[str, object] = {"media": video_urn}
    if title:
        video_content["title"] = title

    body: dict[str, object] = {
        "author": f"urn:li:person:{person_urn}",
        "commentary": _stamp_text(text),
        "visibility": vis_value,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "content": {"media": video_content},
    }
    resp = httpx.post(
        POSTS_URL,
        json=body,
        headers=_rest_headers(access_token),
    )
    resp.raise_for_status()
    urn = resp.headers.get("X-RestLi-Id", "")
    return PostResult(urn=urn, status="created", message=f"Video post published: {urn}")


_OG_PATTERN = re.compile(
    r'<meta\s+(?:[^>]*?\s+)?'
    r'(?:property|name)=["\']og:(\w+)["\']'
    r'\s+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_OG_PATTERN_REVERSED = re.compile(
    r'<meta\s+(?:[^>]*?\s+)?'
    r'content=["\']([^"\']*)["\']'
    r'\s+(?:[^>]*?\s+)?'
    r'(?:property|name)=["\']og:(\w+)["\']',
    re.IGNORECASE,
)


def fetch_link_preview(url: str) -> LinkPreview:
    """Fetch Open Graph metadata from a URL to preview how LinkedIn will render it."""
    try:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=15,
            headers={"User-Agent": "LinkedInBot/1.0"},
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return LinkPreview(url=url, description=f"Could not fetch URL: {e}")

    html = resp.text[:50000]
    og: dict[str, str] = {}
    for match in _OG_PATTERN.finditer(html):
        prop, content = match.group(1).lower(), match.group(2)
        if prop not in og:
            og[prop] = content
    for match in _OG_PATTERN_REVERSED.finditer(html):
        content, prop = match.group(1), match.group(2).lower()
        if prop not in og:
            og[prop] = content

    return LinkPreview(
        url=url,
        title=og.get("title", ""),
        description=og.get("description", ""),
        image=og.get("image", ""),
        site_name=og.get("site_name", ""),
    )
