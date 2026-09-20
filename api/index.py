import os
import sys
import traceback

# Add project root directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "academy_core.settings")

_django_app = None
_init_error = None

try:
    from academy_core.wsgi import application as _django_app
except Exception:
    _init_error = traceback.format_exc()
    print(_init_error, file=sys.stderr)


def app(environ, start_response):
    if _init_error:
        start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
        return [_init_error.encode("utf-8")]
    try:
        return _django_app(environ, start_response)
    except Exception:
        err = traceback.format_exc()
        print(err, file=sys.stderr)
        start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
        return [err.encode("utf-8")]
