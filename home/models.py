from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum
#Create your models here.
SELECT_CATEGORY_CHOICES = [
    ("Food","Food"),
    ("Travel","Travel"),
    ("Shopping","Shopping"),
    ("Necessities","Necessities"),
    ("Entertainment","Entertainment"),
    ("Other","Other")
 ]
ADD_EXPENSE_CHOICES = [
     ("Expense","Expense"),
     ("Income","Income")
 ]
PROFESSION_CHOICES =[
    ("Employee","Employee"),
    ("Business","Business"),
    ("Student","Student"),
    ("Other","Other")
]
class Addmoney_info(models.Model):
    user = models.ForeignKey(User,default = 1, on_delete=models.CASCADE)
    add_money = models.CharField(max_length = 10 , choices = ADD_EXPENSE_CHOICES )
    quantity = models.BigIntegerField()
    Date = models.DateField(default = now)
    Category = models.CharField( max_length = 20, choices = SELECT_CATEGORY_CHOICES , default ='Food')
    class Meta:
        db_table:'addmoney'


class ToolHistory(models.Model):
    TOOL_CHOICES = [
        ('notepad', 'Notepad'),
        ('paint', 'Paint'),
    ]

    user = models.ForeignKey(User, default=1, on_delete=models.CASCADE)
    tool_type = models.CharField(max_length=20, choices=TOOL_CHOICES)
    title = models.CharField(max_length=120)
    content = models.TextField(blank=True, default='')
    image = models.ImageField(upload_to='tool_history', blank=True, null=True)
    created_at = models.DateTimeField(default=now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_tool_type_display()} - {self.title}'


class LoginHistory(models.Model):
    user = models.ForeignKey(User, default=1, on_delete=models.CASCADE)
    login_at = models.DateTimeField(default=now)
    ip_address = models.CharField(max_length=64, blank=True, default='')
    user_agent = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-login_at']

    def __str__(self):
        return f'{self.user.username} @ {self.login_at}'
        
class UserProfile(models.Model):
    user = models.OneToOneField(User,on_delete=models.CASCADE)
    profession = models.CharField(max_length = 10, choices=PROFESSION_CHOICES)
    Savings = models.IntegerField( null=True, blank=True)
    income = models.BigIntegerField(null=True, blank=True)
    image = models.ImageField(upload_to='profile_image',blank=True)
    # New settings fields for enhanced Settings page
    currency = models.CharField(max_length=10, default='USD', blank=True)
    dark_mode = models.BooleanField(default=False)
    budget_limit = models.BigIntegerField(null=True, blank=True)
    notifications_enabled = models.BooleanField(default=True)
    reminders_time = models.CharField(max_length=50, null=True, blank=True)
    categories = models.TextField(blank=True, default='')
    pin_enabled = models.BooleanField(default=False)
    biometric_enabled = models.BooleanField(default=False)
    backup_enabled = models.BooleanField(default=False)
    last_backup = models.DateTimeField(null=True, blank=True)
    def __str__(self):
       return self.user.username



       