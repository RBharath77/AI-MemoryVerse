import html
import logging
import re
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.ssrf import validate_and_resolve_url_safe

logger = logging.getLogger(__name__)


class WebpageImporter:
    """Safely fetches and extracts clean text content from external web URLs."""

    @staticmethod
    def _clean_html(raw_html: str) -> tuple[str, str]:
        """Extract title and clean readable text from HTML markup."""
        # 1. Extract Title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "Imported Webpage"
        title = html.unescape(title)

        # 2. Strip script, style, header, footer, nav tags
        cleaned = re.sub(
            r"<(script|style|nav|header|footer|aside|noscript)[^>]*>.*?</\1>",
            " ",
            raw_html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # 3. Replace common block tags with newlines
        cleaned = re.sub(r"<(p|div|h[1-6]|li|br|tr)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)

        # 4. Strip all remaining HTML tags
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)

        # 5. Normalize whitespace
        lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
        readable_text = "\n\n".join(lines)
        return title, readable_text

    @classmethod
    async def import_url(cls, url: str) -> dict[str, Any]:
        """Validate SSRF safety, download public webpage, and extract content."""
        safe_url, _ = validate_and_resolve_url_safe(url)

        headers = {
            "User-Agent": "AI-MemoryVerse-Bot/1.0 (+https://ai-memoryverse.onrender.com)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
        }

        try:
            current_target = safe_url
            async with httpx.AsyncClient(
                timeout=12.0,
                follow_redirects=False,
            ) as client:
                resp = None
                for redirect_hop in range(4):  # Allow max 3 redirects
                    resp = await client.get(current_target, headers=headers)
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            break
                        # Resolve relative URLs and re-verify SSRF safety for destination
                        resolved_url = str(httpx.URL(current_target).join(location))
                        current_target, _ = validate_and_resolve_url_safe(resolved_url)
                    else:
                        break

                if resp is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No response received from target URL.",
                    )

                # Validate status
                if resp.status_code >= 400:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target server returned HTTP error {resp.status_code}.",
                    )

                # Validate content length (< 5MB)
                content = resp.text
                if len(content.encode("utf-8")) > 5 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Webpage content exceeds 5 MB limit.",
                    )

                title, text = cls._clean_html(content)
                word_count = len(text.split())

                return {
                    "url": safe_url,
                    "title": title[:200],
                    "content": text[:50000],  # Cap at 50,000 characters
                    "word_count": word_count,
                }
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Request to target URL timed out.",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to connect to target URL: {str(e)}",
            )
