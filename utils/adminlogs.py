from dashboard.models import AdminActivityLog


def admin_log_activity(user, description, actions):
    """
    Log basic admin activity
    
    Args:
        user: User instance
        description: Description of the activity
        actions: Action type from AdminActivityLog.ActionType choices
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=actions,
            description=description
        )
    except Exception as e:
        print(f"Error in admin_log_activity: {e}")


def admin_credit_activity(user, description, actions, amount=None):
    """
    Log admin credit-related activity with amount
    
    Args:
        user: User instance
        description: Description of the activity
        actions: Action type from AdminActivityLog.ActionType choices
        amount: Amount involved in the transaction (optional)
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=actions,
            description=description,
            amount=amount
        )
    except Exception as e:
        print(f"Error in admin_credit_activity: {e}")
        raise


def admin_purchase_activity(user, description, amount):
    """
    Log admin purchase activity
    
    Args:
        user: User instance
        description: Description of the purchase
        amount: Purchase amount
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.PURCHASE,
            description=description,
            amount=amount
        )
    except Exception as e:
        print(f"Error in admin_purchase_activity: {e}")
        raise


def admin_refund_activity(user, description, amount):
    """
    Log admin refund activity
    
    Args:
        user: User instance
        description: Description of the refund
        amount: Refund amount
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.REFUND,
            description=description,
            amount=amount
        )
    except Exception as e:
        print(f"Error in admin_refund_activity: {e}")
        raise


def admin_login_activity(user):
    """
    Log admin login activity
    
    Args:
        user: User instance
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.LOGGEDIN,
            description=f"Admin {user.username} logged in"
        )
    except Exception as e:
        print(f"Error in admin_login_activity: {e}")


def admin_logout_activity(user):
    """
    Log admin logout activity
    
    Args:
        user: User instance
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.LOGGEDOUT,
            description=f"Admin {user.username} logged out"
        )
    except Exception as e:
        print(f"Error in admin_logout_activity: {e}")


def admin_password_change_activity(user):
    """
    Log admin password change activity
    
    Args:
        user: User instance
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.PASSWORDCHANGE,
            description=f"Admin {user.username} changed password"
        )
    except Exception as e:
        print(f"Error in admin_password_change_activity: {e}")


def admin_subscription_cancel_activity(user, description):
    """
    Log admin subscription cancellation
    
    Args:
        user: User instance
        description: Description of the cancellation
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.CANCELED,
            description=description
        )
    except Exception as e:
        print(f"Error in admin_subscription_cancel_activity: {e}")
        raise


def admin_failed_activity(user, description):
    """
    Log failed admin activity
    
    Args:
        user: User instance
        description: Description of what failed
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.FAILED,
            description=description
        )
    except Exception as e:
        print(f"Error in admin_failed_activity: {e}")


def admin_update_activity(user, description):
    """
    Log admin update activity
    
    Args:
        user: User instance
        description: Description of what was updated
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.UPDATED,
            description=description
        )
    except Exception as e:
        print(f"Error in admin_update_activity: {e}")


def admin_create_activity(user, description):
    """
    Log admin create activity
    
    Args:
        user: User instance
        description: Description of what was created
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.CREATED,
            description=description
        )
    except Exception as e:
        print(f"Error in admin_create_activity: {e}")


def admin_delete_activity(user, description):
    """
    Log admin delete activity
    
    Args:
        user: User instance
        description: Description of what was deleted
    """
    try:
        AdminActivityLog.objects.create(
            user=user,
            actions=AdminActivityLog.ActionType.DELETED,
            description=description
        )
    except Exception as e:
        print(f"Error in admin_delete_activity: {e}")