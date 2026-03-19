"""FinMail repositories -- data access for emails."""

from datetime import UTC, datetime

from sqlalchemy import func

from finbot.core.data.repositories import NamespacedRepository
from finbot.mcp.servers.finmail.models import Email


class EmailRepository(NamespacedRepository):
    """Unified repository for all emails (vendor and admin inboxes)."""

    def create_email(
        self,
        inbox_type: str,
        subject: str,
        body: str,
        message_type: str,
        sender_name: str,
        vendor_id: int | None = None,
        direction: str = "outbound",
        channel: str = "email",
        sender_type: str = "agent",
        from_address: str | None = None,
        related_invoice_id: int | None = None,
        metadata_json: str | None = None,
        to_addresses: str | None = None,
        cc_addresses: str | None = None,
        bcc_addresses: str | None = None,
        recipient_role: str | None = None,
    ) -> Email:
        """Create an email in the specified inbox."""
        msg = Email(
            namespace=self.namespace,
            inbox_type=inbox_type,
            vendor_id=vendor_id,
            direction=direction,
            message_type=message_type,
            channel=channel,
            subject=subject,
            body=body,
            sender_name=sender_name,
            sender_type=sender_type,
            from_address=from_address,
            related_invoice_id=related_invoice_id,
            metadata_json=metadata_json,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            bcc_addresses=bcc_addresses,
            recipient_role=recipient_role,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    # -- Vendor inbox reads (scoped to a specific vendor) --

    def list_vendor_emails(
        self,
        vendor_id: int,
        message_type: str | None = None,
        is_read: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Email]:
        query = self._add_namespace_filter(self.db.query(Email), Email).filter(
            Email.inbox_type == "vendor", Email.vendor_id == vendor_id
        )
        if message_type:
            query = query.filter(Email.message_type == message_type)
        if is_read is not None:
            query = query.filter(Email.is_read == is_read)
        return (
            query.order_by(Email.created_at.desc(), Email.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_vendor_email_stats(self, vendor_id: int) -> dict:
        base = self._add_namespace_filter(self.db.query(Email), Email).filter(
            Email.inbox_type == "vendor", Email.vendor_id == vendor_id
        )
        total = base.count()
        unread = base.filter(Email.is_read == False).count()
        type_counts = (
            self._add_namespace_filter(
                self.db.query(Email.message_type, func.count(Email.id)), Email
            )
            .filter(Email.inbox_type == "vendor", Email.vendor_id == vendor_id)
            .group_by(Email.message_type)
            .all()
        )
        return {
            "total": total,
            "unread": unread,
            "by_type": {t: c for t, c in type_counts},
        }

    def get_vendor_unread_count(self, vendor_id: int) -> int:
        return (
            self._add_namespace_filter(self.db.query(Email), Email)
            .filter(
                Email.inbox_type == "vendor",
                Email.vendor_id == vendor_id,
                Email.is_read == False,
            )
            .count()
        )

    def mark_all_vendor_as_read(self, vendor_id: int) -> int:
        now = datetime.now(UTC)
        count = (
            self._add_namespace_filter(self.db.query(Email), Email)
            .filter(
                Email.inbox_type == "vendor",
                Email.vendor_id == vendor_id,
                Email.is_read == False,
            )
            .update({"is_read": True, "read_at": now}, synchronize_session="fetch")
        )
        self.db.commit()
        return count

    # -- Admin inbox reads (scoped to namespace) --

    def list_admin_emails(
        self,
        message_type: str | None = None,
        is_read: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Email]:
        query = self._add_namespace_filter(self.db.query(Email), Email).filter(
            Email.inbox_type == "admin"
        )
        if message_type:
            query = query.filter(Email.message_type == message_type)
        if is_read is not None:
            query = query.filter(Email.is_read == is_read)
        return (
            query.order_by(Email.created_at.desc(), Email.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_admin_email_stats(self) -> dict:
        base = self._add_namespace_filter(self.db.query(Email), Email).filter(
            Email.inbox_type == "admin"
        )
        total = base.count()
        unread = base.filter(Email.is_read == False).count()
        type_counts = (
            self._add_namespace_filter(
                self.db.query(Email.message_type, func.count(Email.id)), Email
            )
            .filter(Email.inbox_type == "admin")
            .group_by(Email.message_type)
            .all()
        )
        return {
            "total": total,
            "unread": unread,
            "by_type": {t: c for t, c in type_counts},
        }

    def mark_all_admin_as_read(self) -> int:
        now = datetime.now(UTC)
        count = (
            self._add_namespace_filter(self.db.query(Email), Email)
            .filter(Email.inbox_type == "admin", Email.is_read == False)
            .update({"is_read": True, "read_at": now}, synchronize_session="fetch")
        )
        self.db.commit()
        return count

    # -- External / dead-drop emails (unresolvable addresses) --

    def list_external_emails(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Email]:
        """List external emails."""
        return (
            self._add_namespace_filter(self.db.query(Email), Email)
            .filter(Email.inbox_type == "external")
            .order_by(Email.created_at.desc(), Email.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_external_email_stats(self) -> dict:
        """Get statistics for external emails."""
        base = self._add_namespace_filter(self.db.query(Email), Email).filter(
            Email.inbox_type == "external"
        )
        total = base.count()
        unread = base.filter(Email.is_read == False).count()
        return {"total": total, "unread": unread}

    # -- Shared operations --

    def get_email(self, email_id: int) -> Email | None:
        return self._add_namespace_filter(
            self.db.query(Email).filter(Email.id == email_id), Email
        ).first()

    def mark_as_read(self, email_id: int) -> Email | None:
        msg = self.get_email(email_id)
        if not msg or msg.is_read:
            return msg
        msg.is_read = True
        msg.read_at = datetime.now(UTC)
        self.db.commit()
        return msg
