from dashboard.models import UserActivityLog


def user_log_activity(user, description, actions):
    """
    Log basic user activity
    
    Args:
        user: User instance
        description: Description of the activity
        actions: Action type from UserActivityLog.ActionType choices
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=actions,
            description=description
        )
    except Exception as e:
        print(f"Error in user_log_activity: {e}")


def user_credit_activity(user, description, actions, amount=None):
    """
    Log user credit-related activity with amount
    
    Args:
        user: User instance
        description: Description of the activity
        actions: Action type from UserActivityLog.ActionType choices
        amount: Amount involved in the transaction (optional)
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=actions,
            description=description,
            amount=amount
        )
    except Exception as e:
        print(f"Error in user_credit_activity: {e}")
        raise


def user_purchase_activity(user, description, amount):
    """
    Log user purchase activity
    
    Args:
        user: User instance
        description: Description of the purchase
        amount: Purchase amount
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=UserActivityLog.ActionType.PURCHASE,
            description=description,
            amount=amount
        )
    except Exception as e:
        print(f"Error in user_purchase_activity: {e}")
        raise


def user_refund_activity(user, description, amount):
    """
    Log user refund activity
    
    Args:
        user: User instance
        description: Description of the refund
        amount: Refund amount
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=UserActivityLog.ActionType.REFUND,
            description=description,
            amount=amount
        )
    except Exception as e:
        print(f"Error in user_refund_activity: {e}")
        raise


def user_login_activity(user):
    """
    Log user login activity
    
    Args:
        user: User instance
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=UserActivityLog.ActionType.LOGGEDIN,
            description=f"User {user.username} logged in"
        )
    except Exception as e:
        print(f"Error in user_login_activity: {e}")


def user_logout_activity(user):
    """
    Log user logout activity
    
    Args:
        user: User instance
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=UserActivityLog.ActionType.LOGGEDOUT,
            description=f"User {user.username} logged out"
        )
    except Exception as e:
        print(f"Error in user_logout_activity: {e}")


def user_password_change_activity(user):
    """
    Log user password change activity
    
    Args:
        user: User instance
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=UserActivityLog.ActionType.PASSWORDCHANGE,
            description=f"User {user.username} changed password"
        )
    except Exception as e:
        print(f"Error in user_password_change_activity: {e}")


def user_subscription_cancel_activity(user, description):
    """
    Log user subscription cancellation
    
    Args:
        user: User instance
        description: Description of the cancellation
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=UserActivityLog.ActionType.CANCELED,
            description=description
        )
    except Exception as e:
        print(f"Error in user_subscription_cancel_activity: {e}")
        raise


def user_failed_activity(user, description):
    """
    Log failed user activity
    
    Args:
        user: User instance
        description: Description of what failed
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=UserActivityLog.ActionType.FAILED,
            description=description
        )
    except Exception as e:
        print(f"Error in user_failed_activity: {e}")


def user_update_activity(user, description):
    """
    Log user update activity
    
    Args:
        user: User instance
        description: Description of what was updated
    """
    try:
        UserActivityLog.objects.create(
            user=user,
            actions=UserActivityLog.ActionType.UPDATED,
            description=description
        )
    except Exception as e:
        print(f"Error in user_update_activity: {e}")