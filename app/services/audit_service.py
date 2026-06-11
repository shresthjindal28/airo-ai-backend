import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


class AuditService:

    @staticmethod
    def log_doctor_action(
        db: Session,
        *,
        doctor_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
    ) -> None:
        db.execute(
            text(
                """
                INSERT INTO audit_logs (
                    id, actor_type, actor_id, action, resource_type,
                    resource_id, doctor_id, created_at
                )
                VALUES (
                    :id, 'doctor', :actor_id, :action, :resource_type,
                    :resource_id, :doctor_id, NOW()
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "actor_id": str(doctor_id),
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "doctor_id": str(doctor_id),
            },
        )
        db.commit()
