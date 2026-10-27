"""
HTML email templates (Phase 6B, standardized layout in Module 3 Phase 5b).

A single shared, responsive, inline-styled layout that every
notification email uses, in a consistent order: company branding,
accent/status banner, greeting + main content, a summary/details card,
an optional CTA button, a support section, and a footer. Deliberately
built with plain Python string formatting rather than a templating
engine -- jinja2 isn't already a project dependency, and these
templates are simple enough not to need one. Every value interpolated
here comes from already-validated model data or caller-supplied
primitives; nothing here executes user input as a template.

Kept in its own module (not inside notification_service.py) so the
"what does this email look like" concern is separate from "when do we
send it".
"""
from datetime import datetime, timezone
from typing import Optional

from app.config.settings import settings

_BRAND_RED = "#E50914"
_DARK_SLATE = "#1e293b"
_MUTED = "#64748b"
_BORDER = "#e2e8f0"

# Phase 5b: named accent colors for the status banner -- callers pass
# one of these keys (or omit accent entirely for a neutral/no-banner
# email), never a raw color, so every template stays visually
# consistent rather than picking arbitrary one-off colors.
ACCENT_COLORS = {
    "success": "#16a34a",
    "danger": "#dc2626",
    "warning": "#d97706",
    "info": _BRAND_RED,
}


def render_email(
    *,
    preheader: str,
    heading: str,
    body_html: str,
    accent: Optional[str] = None,
    accent_label: Optional[str] = None,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
) -> str:
    """
    Wraps `body_html` (already-built greeting + main content + details
    card -- see the per-event builders below) in the shared layout.
    Uses inline styles throughout since many email clients strip
    <style> blocks; table-based layout for the widest client
    compatibility.

    `accent` is one of ACCENT_COLORS' keys (or None for no status
    banner at all -- the exact previous look, for full backward
    compatibility with any caller not using this).

    A CTA button is rendered only when *both* `cta_label` and
    `cta_url` are given -- never invented for emails that don't
    naturally call for an action.
    """
    accent_color = ACCENT_COLORS.get(accent) if accent else None
    banner_block = ""
    if accent_color and accent_label:
        banner_block = f"""
          <tr>
            <td style="background-color:{accent_color};padding:10px 32px;">
              <p style="color:#ffffff;font-size:12px;font-weight:bold;letter-spacing:0.05em;margin:0;text-transform:uppercase;">{accent_label}</p>
            </td>
          </tr>"""

    cta_block = ""
    if cta_label and cta_url:
        cta_block = f"""
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:24px;">
                <tr>
                  <td style="background-color:{_BRAND_RED};border-radius:6px;">
                    <a href="{cta_url}" style="display:inline-block;padding:12px 24px;color:#ffffff;font-size:14px;font-weight:bold;text-decoration:none;">{cta_label}</a>
                  </td>
                </tr>
              </table>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:Helvetica,Arial,sans-serif;">
  <span style="display:none;max-height:0;overflow:hidden;">{preheader}</span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;max-width:600px;width:100%;">
          <tr>
            <td style="background-color:{_DARK_SLATE};padding:24px 32px;">
              <img src="{settings.COMPANY_LOGO_URL}" alt="{settings.COMPANY_NAME}" height="28" style="display:block;border:0;" />
            </td>
          </tr>
          {banner_block}
          <tr>
            <td style="padding:32px;">
              <h1 style="color:{_DARK_SLATE};font-size:20px;margin:0 0 16px 0;">{heading}</h1>
              <div style="color:{_DARK_SLATE};font-size:14px;line-height:1.6;">
                {body_html}
              </div>
              {cta_block}
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px;border-top:1px solid {_BORDER};">
              <p style="color:{_MUTED};font-size:12px;margin:0 0 4px 0;">
                Questions? Contact us at <a href="mailto:{settings.SUPPORT_EMAIL}" style="color:{_BRAND_RED};">{settings.SUPPORT_EMAIL}</a>
                or visit <a href="{settings.COMPANY_WEBSITE}" style="color:{_BRAND_RED};">{settings.COMPANY_WEBSITE}</a>.
              </p>
              <p style="color:{_MUTED};font-size:12px;margin:0;">
                &copy; {datetime.now(timezone.utc).year} {settings.COMPANY_NAME}. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def detail_row(label: str, value: str) -> str:
    return (
        f'<tr><td style="color:{_MUTED};padding:4px 12px 4px 0;white-space:nowrap;">{label}</td>'
        f'<td style="color:{_DARK_SLATE};font-weight:bold;padding:4px 0;">{value}</td></tr>'
    )


def detail_table(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    body = "".join(detail_row(label, value) for label, value in rows)
    return f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:12px;font-size:14px;">{body}</table>'
