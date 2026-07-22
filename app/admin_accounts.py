"""
Hardcoded email -> role map for accounts that skip directorate self-selection.
Edit this file directly (and redeploy) to add or change a DG/Registrar/Super
Admin account. Never exposed via any API endpoint.
"""
from app.models import UserRole

ADMIN_ACCOUNTS: dict[str, UserRole] = {
    # "name@gslaw.edu.gh": UserRole.DG,
    # "name@gslaw.edu.gh": UserRole.REGISTRAR,
    # "name@gslaw.edu.gh": UserRole.SUPER_ADMIN,
}


def get_admin_role(email: str) -> UserRole | None:
    return ADMIN_ACCOUNTS.get(email.lower().strip())
