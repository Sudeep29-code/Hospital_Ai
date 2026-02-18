from flask import session, redirect

def admin_required(f):
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect("/admin/login")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper
