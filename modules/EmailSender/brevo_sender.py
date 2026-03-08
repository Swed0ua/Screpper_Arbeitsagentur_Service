"""Brevo (Sendinblue) transactional email via Messaging API."""

import asyncio
from typing import Any, Dict, List, Optional
import requests

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(
    api_key: str,
    sender: Dict[str, str],
    to: List[Dict[str, str]],
    subject: str,
    *,
    html_content: Optional[str] = None,
    text_content: Optional[str] = None,
    template_id: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
    reply_to: Optional[Dict[str, str]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Send one transactional email. Returns {"messageId": "..."}.
    Exactly one of html_content, text_content, template_id must be set.
    """
    payload: Dict[str, Any] = {"sender": sender, "to": to, "subject": subject}
    if html_content is not None:
        payload["htmlContent"] = html_content
    elif text_content is not None:
        payload["textContent"] = text_content
    elif template_id is not None:
        payload["templateId"] = template_id
    else:
        raise ValueError("Provide one of: html_content, text_content, template_id")
    if params:
        payload["params"] = params
    if reply_to:
        payload["replyTo"] = reply_to
    if tags:
        payload["tags"] = tags

    resp = requests.post(
        BREVO_URL,
        json=payload,
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


class BrevoSender:
    def __init__(self, api_key: str, sender_email: str, sender_name: str = ""):
        self.api_key = api_key
        self.sender = {"email": sender_email, "name": sender_name or sender_email}

    def send(
        self,
        to: List[Dict[str, str]],
        subject: str,
        *,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        template_id: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
        reply_to: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return send_email(
            self.api_key,
            self.sender,
            to,
            subject,
            html_content=html_content,
            text_content=text_content,
            template_id=template_id,
            params=params,
            reply_to=reply_to,
            tags=tags,
        )

    async def send_async(
        self,
        to: List[Dict[str, str]],
        subject: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self.send, to, subject, **kwargs)

    async def send_batch_async(
        self,
        emails: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """emails: list of dicts with to, subject, and html_content/text_content/template_id + optional params."""
        results = await asyncio.gather(
            *[
                self.send_async(
                    to=em["to"],
                    subject=em["subject"],
                    html_content=em.get("html_content"),
                    text_content=em.get("text_content"),
                    template_id=em.get("template_id"),
                    params=em.get("params"),
                )
                for em in emails
            ],
            return_exceptions=True,
        )
        out = []
        for r in results:
            if isinstance(r, Exception):
                out.append({"error": str(r)})
            else:
                out.append(r)
        return out