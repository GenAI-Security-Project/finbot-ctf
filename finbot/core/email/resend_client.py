"""Resend email service implementation"""

import logging

from finbot.config import settings
from finbot.core.email.base import EmailService

logger = logging.getLogger(__name__)

resend = None  # pylint: disable=invalid-name

# avoiding import errors when not using resend
if settings.EMAIL_PROVIDER == "resend":
    # pylint: disable=import-outside-toplevel
    import resend

    resend.api_key = settings.RESEND_API_KEY


class ResendEmailService(EmailService):
    """Email service using Resend API"""

    def __init__(self):
        self._resend = resend

    async def send_magic_link(self, to_email: str, magic_link: str) -> bool:
        """Send magic link email via Resend"""
        try:
            self._resend.Emails.send(
                {
                    "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
                    "to": [to_email],
                    "subject": "Sign in to OWASP ASI FinBot CTF",
                    "html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #D4AF37;">Sign in to OWASP ASI FinBot CTF</h2>
                        <p>Click the button below to sign in. This link expires in {settings.MAGIC_LINK_EXPIRY_MINUTES} minutes.</p>
                        <p style="margin: 24px 0;">
                            <a href="{magic_link}" style="display: inline-block; padding: 12px 24px; background-color: #D4AF37; color: #0F0F0F; text-decoration: none; border-radius: 6px; font-weight: bold;">
                                Sign In
                            </a>
                        </p>
                        <p style="color: #666; font-size: 12px;">
                            If you didn't request this email, you can safely ignore it.
                        </p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
                        <p style="color: #999; font-size: 11px;">
                            OWASP ASI FinBot CTF
                        </p>
                    </div>
                """,
                }
            )
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to send email via Resend: %s", e)
            return False
