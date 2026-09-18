import os
import sys
from pathlib import Path

# Set up paths so Django can locate all apps and modules
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academy_core.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
app = application
