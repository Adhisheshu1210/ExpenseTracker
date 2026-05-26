import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ExpenseTracker.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth.models import User

user = User.objects.first()
if not user:
    print('NoUser')
    raise SystemExit(0)

client = Client()
client.force_login(user)
session = client.session
session['is_logged'] = True
session['user_id'] = user.id
session.save()

response = client.get('/expense_edit/39')
print(response.status_code)
print('expenseForm' in response.content.decode('utf-8', errors='ignore'))
