"""
Hardcoded email -> role map for accounts that skip directorate self-selection.
Edit this file directly (and redeploy) to add or change a DG/Registrar/Super
Admin account. Never exposed via any API endpoint.
"""
from app.models import UserRole

SUPER_ADMIN_EMAIL = "ndzreke-poku@gslaw.edu.gh"

ADMIN_ACCOUNTS: dict[str, UserRole] = {
    SUPER_ADMIN_EMAIL: UserRole.SUPER_ADMIN,
    # "name@gslaw.edu.gh": UserRole.DG,
    # "name@gslaw.edu.gh": UserRole.REGISTRAR,
}

# Emails allowed to sign in from outside the @gslaw.edu.gh domain, for
# testing the DG/Registrar/staff role-selector without a second Workspace
# mailbox. Combine with a FlexAdmin row (added via the Super Admin page) to
# actually get the "choose your access" prompt on login.
TEST_ACCOUNT_EMAILS: set[str] = {
    "dzrekenathan2002@gmail.com",
}


def get_admin_role(email: str) -> UserRole | None:
    return ADMIN_ACCOUNTS.get(email.lower().strip())


def is_super_admin_email(email: str) -> bool:
    return email.lower().strip() == SUPER_ADMIN_EMAIL


def is_test_account_email(email: str) -> bool:
    return email.lower().strip() in TEST_ACCOUNT_EMAILS