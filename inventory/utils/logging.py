"""
Logging utilities for the inventory system.
"""
import logging
import json
import traceback
import functools
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_action(user, operation_type, details, related_object=None):
    """
    Log an action in the system.
    
    Args:
        user (User): The user performing the action
        operation_type (str): The type of operation (from OperationLog.OPERATION_TYPES)
        details (str): Details about the operation
        related_object (Model, optional): The object related to this operation
    """
    from inventory.models import OperationLog
    
    # Create operation log
    log_entry = OperationLog(
        operator=user,
        operation_type=operation_type,
        details=details
    )
    
    # If related object is provided, link it
    if related_object:
        content_type = ContentType.objects.get_for_model(related_object)
        log_entry.related_content_type = content_type
        log_entry.related_object_id = related_object.id
    else:
        # Handle the case when no related object is provided
        # Get the default content type (User model can be used)
        content_type = ContentType.objects.get_for_model(User)
        log_entry.related_content_type = content_type
        log_entry.related_object_id = user.id  # Use the user's ID as fallback
    
    log_entry.save()
    return log_entry

def log_view_access(operation_type):
    """Decorator to log access to views."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get the result first
            result = view_func(request, *args, **kwargs)
            
            # Don't log for anonymous users
            if request.user.is_authenticated:
                try:
                    # Prepare details
                    details = {
                        'view': view_func.__name__,
                        'path': request.path,
                        'method': request.method,
                        'ip': get_client_ip(request)
                    }
                    
                    # Log the access
                    log_action(
                        user=request.user,
                        operation_type=operation_type,
                        details=f"Accessed {view_func.__name__}: {json.dumps(details)}"
                    )
                except Exception as e:
                    # Just log the error but don't affect the view's execution
                    logger.error(f"Error logging view access: {str(e)}", exc_info=True)
            
            return result
        return wrapper
    return decorator

def log_exception(func):
    """Decorator to log exceptions in functions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 修复：不再尝试在extra中传递args参数，以避免与LogRecord内部的args冲突
            logger.error(
                f"Exception in {func.__name__}: {str(e)}",
                exc_info=True,
                extra={
                    'function_name': func.__name__,
                    'error_message': str(e),
                    'traceback_str': traceback.format_exc()
                }
            )
            raise
    return wrapper 