import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','ExpenseTracker.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth.models import User
import traceback

TARGET_ID = 39

try:
    user = User.objects.first()
    if not user:
        print('NoUser')
        sys.exit(0)
    c = Client()
    c.force_login(user)
    s = c.session
    s['is_logged'] = True
    s['user_id'] = user.id
    s.save()
    path = f'/expense_edit/{TARGET_ID}'
    r = c.get(path)
    print('STATUS', r.status_code)
    content = r.content.decode('utf-8', errors='replace')
    print('LENGTH', len(content))
    print(content[:1000])
except Exception:
    traceback.print_exc()
    sys.exit(2)
