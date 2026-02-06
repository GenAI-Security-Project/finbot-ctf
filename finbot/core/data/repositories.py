"""Data Repositories for FinBot CTF Platform"""

import json
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from finbot.core.auth.session import SessionContext
from finbot.core.data.models import (
    Badge,
    Challenge,
    CTFEvent,
    Invoice,
    UserActivity,
    UserBadge,
    UserChallengeProgress,
    Vendor,
)


class NamespacedRepository:
    """Base Repository for automatic isolation and activity logging"""

    def __init__(self, db: Session, session_context: SessionContext):
        self.db = db
        self.namespace = session_context.namespace
        self.session_context = session_context

    def _add_namespace_filter(self, query, model):
        """Add namespace filter to all queries"""
        return query.filter(model.namespace == self.namespace)

    def _ensure_namespace(self, obj) -> None:
        """Ensure object has correct namespace before saving"""
        if hasattr(obj, "namespace"):
            obj.namespace = self.namespace

    def log_activity(
        self,
        activity_type: str,
        description: str,
        metadata: dict | None = None,
        commit: bool = False,
    ) -> UserActivity:
        """Log user activity

        Args:
            activity_type: Type of activity being logged
            description: Human-readable description
            metadata: Optional metadata dictionary
            commit: Whether to commit immediately (default: False, relies on caller to commit)
        """
        activity = UserActivity(
            namespace=self.namespace,
            user_id=self.session_context.user_id,
            activity_type=activity_type,
            description=description,
            activity_metadata=json.dumps(metadata) if metadata else None,
        )

        self.db.add(activity)
        if commit:
            self.db.commit()
            self.db.refresh(activity)

        return activity


# =============================================================================
# Vendor Repository
# =============================================================================


class VendorRepository(NamespacedRepository):
    """Repository for Vendor model"""

    def create_vendor(
        self,
        company_name: str,
        vendor_category: str,
        industry: str,
        services: str,
        contact_name: str,
        email: str,
        tin: str,
        bank_account_number: str,
        bank_name: str,
        bank_routing_number: str,
        bank_account_holder_name: str,
        phone: str | None = None,
    ) -> Vendor:
        """Create a new vendor with all required fields"""
        vendor = Vendor(
            company_name=company_name,
            vendor_category=vendor_category,
            industry=industry,
            services=services,
            contact_name=contact_name,
            email=email,
            tin=tin,
            bank_account_number=bank_account_number,
            bank_name=bank_name,
            bank_routing_number=bank_routing_number,
            bank_account_holder_name=bank_account_holder_name,
            phone=phone,
            namespace=self.namespace,
            status="pending",
        )
        self.db.add(vendor)
        self.db.commit()
        self.db.refresh(vendor)

        self.log_activity(
            "vendor_created",
            f"Created vendor: {company_name}",
            metadata={
                "vendor_id": vendor.id,
                "company_name": company_name,
                "vendor_category": vendor_category,
                "industry": industry,
            },
            commit=True,
        )

        return vendor

    def get_vendor(self, vendor_id: int) -> Vendor | None:
        """Get vendor by id"""
        return self._add_namespace_filter(
            self.db.query(Vendor).filter(Vendor.id == vendor_id), Vendor
        ).first()

    def list_vendors(self, status: str | None = None) -> list[Vendor] | None:
        """List vendors"""
        query = self._add_namespace_filter(self.db.query(Vendor), Vendor)

        if status:
            query = query.filter(Vendor.status == status)

        return query.order_by(Vendor.created_at.desc()).all()

    def update_vendor(self, vendor_id: int, **updates) -> Vendor | None:
        """Update vendor"""
        vendor = self.get_vendor(vendor_id)
        if not vendor:
            return None

        for key, value in updates.items():
            if hasattr(vendor, key):
                setattr(vendor, key, value)

        vendor.updated_at = datetime.now(UTC)
        self.db.commit()

        self.log_activity(
            "vendor_updated",
            f"Updated vendor: {vendor.company_name}",
            metadata={
                "vendor_id": vendor.id,
                "vendor_name": vendor.company_name,
                "updates": list(updates.keys()),
            },
            commit=True,
        )

        return vendor

    def delete_vendor(self, vendor_id: int) -> bool:
        """Delete vendor"""
        vendor = self.get_vendor(vendor_id)
        if not vendor:
            return False

        vendor_name = vendor.company_name
        vendor_id = vendor.id
        self.db.delete(vendor)
        self.db.commit()

        self.log_activity(
            "vendor_deleted",
            f"Deleted vendor: {vendor_name}",
            metadata={"vendor_id": vendor_id, "vendor_name": vendor_name},
            commit=True,
        )

        return True

    def get_vendor_count(self) -> int:
        """Get count of vendors"""
        return self._add_namespace_filter(self.db.query(Vendor), Vendor).count()

    def set_current_vendor(self, vendor_id: int) -> bool:
        """Set current vendor for user (all sessions)"""
        # Validate vendor belongs to user
        vendor = self.get_vendor(vendor_id)
        if not vendor:
            return False

        # Update vendor context globally
        # avoid circular import; pylint: disable=import-outside-toplevel
        from finbot.core.auth.session import session_manager

        success = session_manager.update_vendor_context(
            self.session_context.session_id, vendor_id
        )

        if success:
            self.log_activity(
                "vendor_switched",
                f"Switched to vendor: {vendor.company_name}",
                metadata={
                    "vendor_id": vendor_id,
                    "company_name": vendor.company_name,
                },
                commit=True,
            )

        return success


# =============================================================================
# Invoice Repository
# =============================================================================


class InvoiceRepository(NamespacedRepository):
    """Invoice repository - Namespaced to user"""

    def __init__(self, db: Session, session_context: SessionContext):
        super().__init__(db, session_context)
        self.current_vendor_id = session_context.current_vendor_id

    # Vendor Scoped Methods for Vendor Portal
    def list_invoices_for_current_vendor(
        self, status: str | None = None
    ) -> list[Invoice]:
        """Vendor portal: List invoices for current vendor only"""
        if not self.current_vendor_id:
            raise ValueError("Vendor context required for this operation")

        query = self._add_namespace_filter(self.db.query(Invoice), Invoice)
        query = query.filter(Invoice.vendor_id == self.current_vendor_id)

        if status:
            query = query.filter(Invoice.status == status)

        return query.order_by(Invoice.created_at.desc()).all()

    def create_invoice_for_current_vendor(self, **invoice_data) -> Invoice:
        """Vendor portal: Create invoice for current vendor"""
        if not self.current_vendor_id:
            raise ValueError("Vendor context required for this operation")

        invoice_data["vendor_id"] = self.current_vendor_id
        invoice_data["namespace"] = self.namespace

        invoice = Invoice(**invoice_data)
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)

        self.log_activity(
            "invoice_created",
            f"Created invoice: {invoice.invoice_number}",
            metadata={
                "invoice_id": invoice.id,
                "vendor_id": self.current_vendor_id,
                "amount": float(invoice.amount),
            },
            commit=True,
        )

        return invoice

    def get_current_vendor_invoice_stats(self) -> dict:
        """Vendor portal: Get invoice stats for current vendor"""
        if not self.current_vendor_id:
            raise ValueError("Vendor context required for this operation")

        query = self._add_namespace_filter(self.db.query(Invoice), Invoice)
        query = query.filter(Invoice.vendor_id == self.current_vendor_id)

        total_count = query.count()
        total_amount = query.with_entities(func.sum(Invoice.amount)).scalar() or 0
        paid_count = query.filter(Invoice.status == "paid").count()
        paid_amount = (
            query.filter(Invoice.status == "paid")
            .with_entities(func.sum(Invoice.amount))
            .scalar()
            or 0
        )

        # Count overdue invoices (due date passed, not paid)
        now = datetime.now(UTC)
        overdue_query = self._add_namespace_filter(self.db.query(Invoice), Invoice)
        overdue_query = overdue_query.filter(
            Invoice.vendor_id == self.current_vendor_id
        )
        overdue_count = (
            overdue_query.filter(Invoice.status != "paid")
            .filter(Invoice.due_date < now)
            .count()
        )

        pending_count = total_count - paid_count

        return {
            "total_count": total_count,
            "total_amount": float(total_amount),
            "paid_count": paid_count,
            "paid_amount": float(paid_amount),
            "pending_count": pending_count,
            "pending_amount": float(total_amount) - float(paid_amount),
            "overdue_count": overdue_count,
        }

    # Admin Portal Methods (cross-vendor within namespace)
    def list_all_invoices_for_user(self, status: str | None = None) -> list[Invoice]:
        """Admin portal: List ALL invoices across all user's vendors"""
        query = self._add_namespace_filter(self.db.query(Invoice), Invoice)

        if status:
            query = query.filter(Invoice.status == status)

        return query.order_by(Invoice.created_at.desc()).all()

    def list_invoices_by_vendor(
        self, status: str | None = None
    ) -> dict[int, list[Invoice]]:
        """Admin portal: Group invoices by vendor"""
        invoices = self.list_all_invoices_for_user(status)

        grouped = {}
        for invoice in invoices:
            vendor_id = invoice.vendor_id
            if vendor_id not in grouped:
                grouped[vendor_id] = []
            grouped[vendor_id].append(invoice)

        return grouped

    def get_invoice_stats_by_vendor(self) -> dict[int, dict]:
        """Admin portal: Get invoice statistics grouped by vendor"""
        stats = (
            self.db.query(
                Invoice.vendor_id,
                func.count(Invoice.id).label("total_count"),
                func.sum(Invoice.amount).label("total_amount"),
                func.count(func.nullif(Invoice.status != "paid", True)).label(
                    "paid_count"
                ),
                func.sum(
                    func.case([(Invoice.status == "paid", Invoice.amount)], else_=0)
                ).label("paid_amount"),
            )
            .filter(Invoice.namespace == self.namespace)
            .group_by(Invoice.vendor_id)
            .all()
        )

        return {
            stat.vendor_id: {
                "total_count": stat.total_count,
                "total_amount": float(stat.total_amount or 0),
                "paid_count": stat.paid_count,
                "paid_amount": float(stat.paid_amount or 0),
                "pending_count": stat.total_count - stat.paid_count,
                "pending_amount": float(stat.total_amount or 0)
                - float(stat.paid_amount or 0),
            }
            for stat in stats
        }

    def get_user_invoice_totals(self) -> dict:
        """Admin portal: Get aggregate invoice totals for user"""
        query = self._add_namespace_filter(self.db.query(Invoice), Invoice)

        total_count = query.count()
        total_amount = query.with_entities(func.sum(Invoice.amount)).scalar() or 0
        paid_count = query.filter(Invoice.status == "paid").count()
        paid_amount = (
            query.filter(Invoice.status == "paid")
            .with_entities(func.sum(Invoice.amount))
            .scalar()
            or 0
        )

        return {
            "total_count": total_count,
            "total_amount": float(total_amount),
            "paid_count": paid_count,
            "paid_amount": float(paid_amount),
            "pending_count": total_count - paid_count,
            "pending_amount": float(total_amount) - float(paid_amount),
        }

    # Flexible Methods (can be used by both portals)
    def list_invoices_for_specific_vendor(
        self, vendor_id: int, status: str | None = None
    ) -> list[Invoice]:
        """List invoices for specific vendor"""
        # Validate vendor belongs to user's namespace
        vendor_repo = VendorRepository(self.db, self.session_context)
        if not vendor_repo.get_vendor(vendor_id):
            raise ValueError("Vendor not found or access denied")

        query = self._add_namespace_filter(self.db.query(Invoice), Invoice)
        query = query.filter(Invoice.vendor_id == vendor_id)

        if status:
            query = query.filter(Invoice.status == status)

        return query.order_by(Invoice.created_at.desc()).all()

    def get_invoice(self, invoice_id: int) -> Invoice | None:
        """Flexible: Get single invoice (validates namespace, not vendor)"""
        return self._add_namespace_filter(
            self.db.query(Invoice).filter(Invoice.id == invoice_id), Invoice
        ).first()

    def update_invoice(self, invoice_id: int, **updates) -> Invoice | None:
        """Flexible: Update invoice (validates namespace)"""
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            return None

        for key, value in updates.items():
            if hasattr(invoice, key):
                setattr(invoice, key, value)

        invoice.updated_at = datetime.now(UTC)
        self.db.commit()

        self.log_activity(
            "invoice_updated",
            f"Updated invoice: {invoice.invoice_number}",
            metadata={
                "invoice_id": invoice.id,
                "vendor_id": invoice.vendor_id,
                "updates": list(updates.keys()),
            },
            commit=True,
        )

        return invoice


# =============================================================================
# User Activity Repository
# =============================================================================


class UserActivityRepository(NamespacedRepository):
    """User activity tracking repository"""

    def log_activity(
        self,
        activity_type: str,
        description: str,
        metadata: dict | None = None,
        commit: bool = True,
    ) -> UserActivity:
        """Log user activity with immediate commit by default"""

        activity = UserActivity(
            namespace=self.namespace,
            user_id=self.session_context.user_id,
            activity_type=activity_type,
            description=description,
            activity_metadata=json.dumps(metadata) if metadata else None,
        )

        self.db.add(activity)
        if commit:
            self.db.commit()
            self.db.refresh(activity)

        return activity

    def get_user_activities(self, limit: int = 50) -> list[UserActivity]:
        """Get user activities in their namespace"""
        return (
            self._add_namespace_filter(
                self.db.query(UserActivity).filter(
                    UserActivity.user_id == self.session_context.user_id
                ),
                UserActivity,
            )
            .order_by(UserActivity.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_activity_stats(self) -> dict:
        """Get activity statistics for user"""
        query = self._add_namespace_filter(
            self.db.query(UserActivity).filter(
                UserActivity.user_id == self.session_context.user_id
            ),
            UserActivity,
        )

        total_activities = query.count()

        activity_types = {}
        activity_type_query = (
            query.with_entities(UserActivity.activity_type)
            .group_by(UserActivity.activity_type)
            .all()
        )
        for activity_type_result in activity_type_query:
            activity_type = activity_type_result[0]
            count = query.filter(UserActivity.activity_type == activity_type).count()
            activity_types[activity_type] = count

        return {"total_activities": total_activities, "activity_types": activity_types}


# =============================================================================
# CTF Repositories
# =============================================================================

# =============================================================================
# Challenge Repository
# =============================================================================


class ChallengeRepository:
    """Repository for Challenge definitions (global, not namespaced)"""

    def __init__(self, db: Session):
        self.db = db

    def list_challenges(
        self,
        category: str | None = None,
        difficulty: str | None = None,
        active_only: bool = True,
    ) -> list[Challenge]:
        """List challenges with optional filters"""
        query = self.db.query(Challenge)

        if active_only:
            query = query.filter(Challenge.is_active == True)
        if category:
            query = query.filter(Challenge.category == category)
        if difficulty:
            query = query.filter(Challenge.difficulty == difficulty)

        return query.order_by(Challenge.order_index, Challenge.id).all()

    def get_challenge(self, challenge_id: str) -> Challenge | None:
        """Get challenge by ID"""
        return self.db.query(Challenge).filter(Challenge.id == challenge_id).first()

    def get_categories(self) -> list[str]:
        """Get distinct challenge categories"""
        result = (
            self.db.query(Challenge.category)
            .filter(Challenge.is_active == True)
            .distinct()
            .all()
        )
        return [r[0] for r in result]

    def count_by_category(self) -> dict[str, int]:
        """Count challenges per category"""
        result = (
            self.db.query(Challenge.category, func.count(Challenge.id))
            .filter(Challenge.is_active == True)
            .group_by(Challenge.category)
            .all()
        )
        return {cat: count for cat, count in result}

    def get_total_points(self, challenge_ids: list[str]) -> int:
        """Get total points for given challenge IDs"""
        if not challenge_ids:
            return 0
        return (
            self.db.query(func.sum(Challenge.points))
            .filter(Challenge.id.in_(challenge_ids))
            .scalar()
            or 0
        )


# =============================================================================
# User Challenge Progress Repository
# =============================================================================


class UserChallengeProgressRepository(NamespacedRepository):
    """Repository for user challenge progress (namespaced)"""

    def get_progress(self, challenge_id: str) -> UserChallengeProgress | None:
        """Get user's progress for a specific challenge"""

        return (
            self.db.query(UserChallengeProgress)
            .filter(
                UserChallengeProgress.namespace == self.namespace,
                UserChallengeProgress.user_id == self.session_context.user_id,
                UserChallengeProgress.challenge_id == challenge_id,
            )
            .first()
        )

    def get_or_create_progress(self, challenge_id: str) -> UserChallengeProgress:
        """Get or create user's progress for a challenge"""
        progress = self.get_progress(challenge_id)
        if not progress:
            progress = UserChallengeProgress(
                namespace=self.namespace,
                user_id=self.session_context.user_id,
                challenge_id=challenge_id,
                status="available",
            )
            self.db.add(progress)
            self.db.flush()
        return progress

    def get_all_progress(self) -> list[UserChallengeProgress]:
        """Get all challenge progress for user"""
        return (
            self.db.query(UserChallengeProgress)
            .filter(
                UserChallengeProgress.namespace == self.namespace,
                UserChallengeProgress.user_id == self.session_context.user_id,
            )
            .all()
        )

    def get_progress_map(self) -> dict[str, str]:
        """Get challenge_id -> status mapping for user"""
        progress_list = self.get_all_progress()
        return {p.challenge_id: p.status for p in progress_list}

    def get_completed_challenges(self) -> list[UserChallengeProgress]:
        """Get completed challenges for user"""
        return (
            self.db.query(UserChallengeProgress)
            .filter(
                UserChallengeProgress.namespace == self.namespace,
                UserChallengeProgress.user_id == self.session_context.user_id,
                UserChallengeProgress.status == "completed",
            )
            .all()
        )

    def use_hint(self, challenge_id: str, hint_cost: int) -> UserChallengeProgress:
        """Use a hint for a challenge"""
        progress = self.get_or_create_progress(challenge_id)
        progress.hints_used += 1
        progress.hints_cost += hint_cost
        if progress.status == "available":
            progress.status = "in_progress"

        self.db.commit()

        self.log_activity(
            "challenge_hint_used",
            f"Used hint for challenge: {challenge_id}",
            metadata={
                "challenge_id": challenge_id,
                "hint_number": progress.hints_used,
                "hint_cost": hint_cost,
                "total_hints_cost": progress.hints_cost,
            },
        )

        return progress

    def record_attempt(self, challenge_id: str) -> UserChallengeProgress:
        """Record an attempt on a challenge"""
        progress = self.get_or_create_progress(challenge_id)
        progress.attempts += 1
        if progress.first_attempt_at is None:
            progress.first_attempt_at = datetime.now(UTC)
        if progress.status == "available":
            progress.status = "in_progress"
        self.db.commit()
        return progress

    def mark_completed(
        self,
        challenge_id: str,
        evidence: dict,
        workflow_id: str | None = None,
    ) -> UserChallengeProgress:
        """Mark challenge as completed"""
        progress = self.get_or_create_progress(challenge_id)

        now = datetime.now(UTC)
        progress.status = "completed"
        progress.successful_attempts += 1
        progress.completed_at = now

        if progress.first_attempt_at:
            progress.completion_time_seconds = int(
                (now - progress.first_attempt_at).total_seconds()
            )

        progress.completion_evidence = json.dumps(evidence)
        progress.completion_workflow_id = workflow_id

        self.db.commit()

        self.log_activity(
            "challenge_completed",
            f"Completed challenge: {challenge_id}",
            metadata={
                "challenge_id": challenge_id,
                "attempts": progress.attempts,
                "hints_used": progress.hints_used,
                "completion_time_seconds": progress.completion_time_seconds,
            },
        )

        return progress

    def get_stats(self) -> dict:
        """Get challenge statistics for user"""
        all_progress = self.get_all_progress()

        completed = [p for p in all_progress if p.status == "completed"]
        in_progress = [p for p in all_progress if p.status == "in_progress"]

        return {
            "completed_count": len(completed),
            "completed_ids": [p.challenge_id for p in completed],
            "in_progress_count": len(in_progress),
            "total_attempts": sum(p.attempts for p in all_progress),
            "hints_used": sum(p.hints_used for p in all_progress),
            "hints_cost": sum(p.hints_cost for p in all_progress),
        }


# =============================================================================
# Badge Repository
# =============================================================================


class BadgeRepository:
    """Repository for Badge definitions (global, not namespaced)"""

    def __init__(self, db: Session):
        self.db = db

    def list_badges(
        self,
        category: str | None = None,
        active_only: bool = True,
        include_secret: bool = False,
    ) -> list[Badge]:
        """List badges with optional filters"""

        query = self.db.query(Badge)

        if active_only:
            query = query.filter(Badge.is_active == True)
        if not include_secret:
            query = query.filter(Badge.is_secret == False)
        if category:
            query = query.filter(Badge.category == category)

        return query.order_by(Badge.rarity, Badge.id).all()

    def get_badge(self, badge_id: str) -> Badge | None:
        """Get badge by ID"""
        return self.db.query(Badge).filter(Badge.id == badge_id).first()

    def count_badges(self, include_secret: bool = False) -> int:
        """Count active badges"""
        query = self.db.query(Badge).filter(Badge.is_active == True)
        if not include_secret:
            query = query.filter(Badge.is_secret == False)
        return query.count()

    def get_total_points(self, badge_ids: list[str]) -> int:
        """Get total points for given badge IDs"""
        if not badge_ids:
            return 0
        return (
            self.db.query(func.sum(Badge.points))
            .filter(Badge.id.in_(badge_ids))
            .scalar()
            or 0
        )


# =============================================================================
# User Badge Repository
# =============================================================================


class UserBadgeRepository(NamespacedRepository):
    """Repository for user badges (namespaced)"""

    def get_earned_badges(self) -> list[UserBadge]:
        """Get all badges earned by user"""
        return (
            self.db.query(UserBadge)
            .filter(
                UserBadge.namespace == self.namespace,
                UserBadge.user_id == self.session_context.user_id,
            )
            .order_by(UserBadge.earned_at.desc())
            .all()
        )

    def get_earned_badge_ids(self) -> set[str]:
        """Get set of earned badge IDs"""
        badges = self.get_earned_badges()
        return {b.badge_id for b in badges}

    def has_badge(self, badge_id: str) -> bool:
        """Check if user has earned a specific badge"""
        return (
            self.db.query(UserBadge)
            .filter(
                UserBadge.namespace == self.namespace,
                UserBadge.user_id == self.session_context.user_id,
                UserBadge.badge_id == badge_id,
            )
            .first()
            is not None
        )

    def get_user_badge(self, badge_id: str) -> "UserBadge | None":
        """Get specific user badge"""
        return (
            self.db.query(UserBadge)
            .filter(
                UserBadge.namespace == self.namespace,
                UserBadge.user_id == self.session_context.user_id,
                UserBadge.badge_id == badge_id,
            )
            .first()
        )

    def award_badge(
        self,
        badge_id: str,
        context: dict,
        workflow_id: str | None = None,
    ) -> "UserBadge":
        """Award badge to user (idempotent)"""
        existing = self.get_user_badge(badge_id)
        if existing:
            return existing

        user_badge = UserBadge(
            namespace=self.namespace,
            user_id=self.session_context.user_id,
            badge_id=badge_id,
            earned_at=datetime.now(UTC),
            earning_context=json.dumps(context),
            earning_workflow_id=workflow_id,
        )
        self.db.add(user_badge)
        self.db.commit()

        self.log_activity(
            "badge_earned",
            f"Earned badge: {badge_id}",
            metadata={
                "badge_id": badge_id,
                "workflow_id": workflow_id,
            },
        )

        return user_badge

    def count_earned(self) -> int:
        """Count badges earned by user"""
        return (
            self.db.query(UserBadge)
            .filter(
                UserBadge.namespace == self.namespace,
                UserBadge.user_id == self.session_context.user_id,
            )
            .count()
        )


# =============================================================================
# CTF Event Repository
# =============================================================================


class CTFEventRepository(NamespacedRepository):
    """Repository for CTF activity events (namespaced)"""

    def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        category: str | None = None,
        workflow_id: str | None = None,
        vendor_id: int | None = None,
    ) -> list[CTFEvent]:
        """Get paginated activity events"""
        query = self.db.query(CTFEvent).filter(
            CTFEvent.namespace == self.namespace,
            CTFEvent.user_id == self.session_context.user_id,
        )

        if category:
            query = query.filter(CTFEvent.event_category == category)
        if workflow_id:
            query = query.filter(CTFEvent.workflow_id == workflow_id)
        if vendor_id:
            query = query.filter(CTFEvent.vendor_id == vendor_id)

        return (
            query.order_by(CTFEvent.timestamp.desc()).offset(offset).limit(limit).all()
        )

    def count_events(
        self,
        category: str | None = None,
        workflow_id: str | None = None,
        vendor_id: int | None = None,
    ) -> int:
        """Count events with filters"""
        query = self.db.query(CTFEvent).filter(
            CTFEvent.namespace == self.namespace,
            CTFEvent.user_id == self.session_context.user_id,
        )

        if category:
            query = query.filter(CTFEvent.event_category == category)
        if workflow_id:
            query = query.filter(CTFEvent.workflow_id == workflow_id)
        if vendor_id:
            query = query.filter(CTFEvent.vendor_id == vendor_id)

        return query.count()

    def get_recent_completions(self, limit: int = 5) -> list[CTFEvent]:
        """Get recent challenge completions and badge awards"""
        return (
            self.db.query(CTFEvent)
            .filter(
                CTFEvent.namespace == self.namespace,
                CTFEvent.user_id == self.session_context.user_id,
                (CTFEvent.challenge_id.isnot(None)) | (CTFEvent.badge_id.isnot(None)),
            )
            .order_by(CTFEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_workflow_events(self, workflow_id: str) -> list[CTFEvent]:
        """Get all events for a specific workflow"""
        return (
            self.db.query(CTFEvent)
            .filter(
                CTFEvent.namespace == self.namespace,
                CTFEvent.workflow_id == workflow_id,
            )
            .order_by(CTFEvent.timestamp)
            .all()
        )
