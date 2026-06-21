from __future__ import annotations

from pathlib import Path

import httpx

from .models import PostResult, Profile

API_BASE = "https://api.linkedin.com/v2"
USERINFO_URL = f"{API_BASE}/userinfo"
UGC_POSTS_URL = f"{API_BASE}/ugcPosts"
ASSETS_URL = f"{API_BASE}/assets"

RESTLI_HEADER = {"X-Restli-Protocol-Version": "2.0.0"}


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
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


def _build_ugc_post(
    person_urn: str,
    text: str,
    visibility: str = "PUBLIC",
    media_category: str = "NONE",
    media: list[dict] | None = None,
) -> dict:
    post = {
        "author": f"urn:li:person:{person_urn}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": media_category,
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility,
        },
    }
    if media:
        post["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = media
    return post


def create_text_post(
    access_token: str,
    person_urn: str,
    text: str,
    visibility: str = "PUBLIC",
) -> PostResult:
    """Create a text-only post on LinkedIn."""
    body = _build_ugc_post(person_urn, text, visibility)
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
    media_item: dict = {"status": "READY", "originalUrl": url}
    if title:
        media_item["title"] = {"text": title}
    if description:
        media_item["description"] = {"text": description}

    body = _build_ugc_post(
        person_urn, text, visibility, media_category="ARTICLE", media=[media_item]
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

    media_item: dict = {"status": "READY", "media": asset_urn}
    if title:
        media_item["title"] = {"text": title}
    if description:
        media_item["description"] = {"text": description}

    body = _build_ugc_post(
        person_urn, text, visibility, media_category="IMAGE", media=[media_item]
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
