from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def role_required(*roles):
    """Protege una vista: exige sesión iniciada y uno de los roles indicados.

    Uso: @role_required('leader', 'admin')
    """

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.has_role(*roles):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
