from django.shortcuts import render,HttpResponse,redirect
from django.contrib import messages
from django.contrib.auth import authenticate ,logout
from django.contrib.auth import login as dj_login
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.core.mail import get_connection
from django.conf import settings as django_settings
from .models import Addmoney_info, UserProfile, ToolHistory, LoginHistory
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator, EmptyPage , PageNotAnInteger
from django.db.models import Sum
from django.http import JsonResponse
import datetime
import json
import logging
from collections import defaultdict
from django.utils import timezone
from django.db.models import Max, Min
# Create your views here.
logger = logging.getLogger(__name__)


REPORT_CATEGORIES = ['Food', 'Travel', 'Shopping', 'Necessities', 'Entertainment', 'Others']


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _period_range(days):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days)
    previous_start = start - datetime.timedelta(days=days)
    previous_end = start - datetime.timedelta(days=1)
    return today, start, previous_start, previous_end


def _date_labels(start, end):
    labels = []
    cursor = start
    while cursor <= end:
        labels.append(cursor.strftime('%d %b'))
        cursor += datetime.timedelta(days=1)
    return labels


def _sum_transactions(queryset, kind):
    return sum(item.quantity for item in queryset if item.add_money == kind)


def _transaction_extreme(queryset, kind, field='max'):
    filtered = queryset.filter(add_money=kind)
    if not filtered.exists():
        return None
    item = filtered.order_by('-quantity' if field == 'max' else 'quantity', '-Date' if field == 'max' else 'Date').first()
    return {
        'id': item.id,
        'amount': item.quantity,
        'category': item.Category,
        'date': item.Date,
        'type': item.add_money,
    }


def _period_report(user, days):
    today, start, previous_start, previous_end = _period_range(days)
    current = Addmoney_info.objects.filter(user=user, Date__gte=start, Date__lte=today).order_by('Date')
    previous = Addmoney_info.objects.filter(user=user, Date__gte=previous_start, Date__lte=previous_end).order_by('Date')
    profile = getattr(user, 'userprofile', None)
    savings_value = getattr(profile, 'Savings', 0) or 0

    current_expense = _sum_transactions(current, 'Expense')
    current_income = _sum_transactions(current, 'Income')
    previous_expense = _sum_transactions(previous, 'Expense')
    previous_income = _sum_transactions(previous, 'Income')

    net = savings_value + current_income - current_expense
    balance_left = max(net, 0)
    deficit = abs(net) if net < 0 else 0

    category_totals = {}
    for category in REPORT_CATEGORIES:
        category_totals[category] = sum(
            item.quantity for item in current if item.Category == category and item.add_money == 'Expense'
        )

    total_category_spend = sum(category_totals.values()) or 1
    chart_categories = [category for category, total in category_totals.items() if total > 0]
    chart_category_values = [category_totals[category] for category in chart_categories]

    daily_labels = _date_labels(start, today)
    daily_income = []
    daily_expense = []
    for day_index, label in enumerate(daily_labels):
        current_day = start + datetime.timedelta(days=day_index)
        day_records = [item for item in current if item.Date == current_day]
        daily_income.append(sum(item.quantity for item in day_records if item.add_money == 'Income'))
        daily_expense.append(sum(item.quantity for item in day_records if item.add_money == 'Expense'))

    compare_income_diff = current_income - previous_income
    compare_expense_diff = current_expense - previous_expense

    def _percent_change(current_value, previous_value):
        if previous_value == 0:
            return 100 if current_value > 0 else 0
        return round(((current_value - previous_value) / previous_value) * 100, 1)

    income_change_percent = _percent_change(current_income, previous_income)
    expense_change_percent = _percent_change(current_expense, previous_expense)

    return {
        'current': current,
        'previous': previous,
        'current_expense': current_expense,
        'current_income': current_income,
        'previous_expense': previous_expense,
        'previous_income': previous_income,
        'compare_income_diff': compare_income_diff,
        'compare_expense_diff': compare_expense_diff,
        'income_change_percent': income_change_percent,
        'expense_change_percent': expense_change_percent,
        'balance_left': balance_left,
        'deficit': deficit,
        'savings_value': savings_value,
        'category_totals': category_totals,
        'chart_categories': chart_categories,
        'chart_category_values': chart_category_values,
        'chart_daily_labels': daily_labels,
        'chart_daily_income': daily_income,
        'chart_daily_expense': daily_expense,
        'highest_expense': _transaction_extreme(current, 'Expense', 'max'),
        'lowest_expense': _transaction_extreme(current, 'Expense', 'min'),
        'highest_income': _transaction_extreme(current, 'Income', 'max'),
        'lowest_income': _transaction_extreme(current, 'Income', 'min'),
        'previous_total': previous_expense + previous_income,
        'current_total': current_expense + current_income,
        'transaction_count': current.count(),
        'sum': current_expense,
        'sum1': current_income,
        'x': balance_left,
        'y': deficit,
        'expense_category_data': category_totals,
        'current_balance': balance_left,
        'budget_used': round((current_expense / savings_value) * 100, 1) if savings_value else 0,
    }


def _monthly_series(queryset, year):
    labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    income = []
    expense = []
    for month in range(1, 13):
        month_records = [item for item in queryset if item.Date.year == year and item.Date.month == month]
        income.append(sum(item.quantity for item in month_records if item.add_money == 'Income'))
        expense.append(sum(item.quantity for item in month_records if item.add_money == 'Expense'))
    return labels, income, expense

def home(request):
    if request.session.has_key('is_logged'):
        return redirect('/index')
    return render(request,'landing.html')
   # return HttpResponse('This is home')

def loginpage(request):
    if request.session.has_key('is_logged'):
        return redirect('/index')
    return render(request,'login.html')

def index(request):
    if request.session.has_key('is_logged'):
        user_id = request.session["user_id"]
        user = User.objects.get(id=user_id)
        addmoney_info = Addmoney_info.objects.filter(user=user).order_by('-Date')
        paginator = Paginator(addmoney_info , 4)
        page_number = request.GET.get('page')
        page_obj = Paginator.get_page(paginator,page_number)
        total_income = sum(item.quantity for item in addmoney_info if item.add_money == 'Income')
        total_expense = sum(item.quantity for item in addmoney_info if item.add_money == 'Expense')
        savings_target = getattr(getattr(user, 'userprofile', None), 'Savings', 0) or 0
        monthly_income_target = getattr(getattr(user, 'userprofile', None), 'income', 0) or 0
        current_balance = savings_target + total_income - total_expense
        budget_used = 0 if savings_target <= 0 else min(100, round((total_expense / savings_target) * 100))
        expenses_by_category = defaultdict(int)
        for item in addmoney_info:
            if item.add_money == 'Expense':
                expenses_by_category[item.Category] += item.quantity
        max_category_total = max(expenses_by_category.values()) if expenses_by_category else 0
        category_breakdown = [
            {
                'category': category,
                'total': amount,
                'percent': 0 if max_category_total <= 0 else round((amount / max_category_total) * 100)
            }
            for category, amount in sorted(expenses_by_category.items(), key=lambda entry: entry[1], reverse=True)
        ]
        context = {
           'page_obj' : page_obj,
           'recent_transactions': list(addmoney_info[:5]),
           'total_income': total_income,
           'total_expense': total_expense,
           'current_balance': current_balance,
           'savings_target': savings_target,
           'monthly_income_target': monthly_income_target,
           'budget_used': budget_used,
           'category_breakdown': category_breakdown,
           'transaction_count': addmoney_info.count(),
        }
    #if request.session.has_key('is_logged'):
        return render(request,'index.html',context)
    return redirect('home')
    #return HttpResponse('This is blog')
def register(request):
    return render(request,'register.html')

def reset_password(request):
    if request.method == 'GET':
        email = request.GET.get('email', '').strip().lower()
        if not email:
            messages.error(request, ' Please request a reset link first.')
            return redirect('forgot_password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, ' Email not registered. Please register first.')
            return redirect('register')

        return render(request, 'reset_password.html', {'email': user.email})

    email = request.POST.get('email', '').strip().lower()
    new_password = request.POST.get('new_password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not email or not new_password or not confirm_password:
        messages.error(request, ' Please fill all fields to update your password.')
        return redirect(f'/reset_password/?email={email}')

    if new_password != confirm_password:
        messages.error(request, ' Password and confirm password do not match.')
        return redirect(f'/reset_password/?email={email}')

    if len(new_password) < 8:
        messages.error(request, ' Password must be at least 8 characters long.')
        return redirect(f'/reset_password/?email={email}')

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, ' Email not registered. Please register first.')
        return redirect('register')

    user.set_password(new_password)
    user.save(update_fields=['password'])
    messages.success(request, ' Password updated successfully. Please login again.')
    return redirect('login')

def forgot_password(request):
    if request.method == 'GET':
        return render(request, 'forgot_password.html')

    email = request.POST.get('email', '').strip().lower()

    if not email:
        messages.error(request, ' Please enter your registered email address.')
        return redirect('forgot_password')

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, ' Email not registered. Please register first.')
        return redirect('register')

    try:
        sender_email = django_settings.EMAIL_HOST_USER or django_settings.DEFAULT_FROM_EMAIL or 'noreply@expensetracker.local'
        connection = get_connection(fail_silently=False)
        reset_link = request.build_absolute_uri(f'/reset_password/?email={user.email}')
        email_message = EmailMessage(
            subject='ExpenseTracker password reset link',
            body=(
                'We received a password reset request for your ExpenseTracker account.\n\n'
                f'Open this link to set a new password:\n{reset_link}\n\n'
                'If you did not request this, you can safely ignore this email.'
            ),
            from_email=sender_email,
            to=[user.email],
            connection=connection,
        )
        email_message.send(fail_silently=False)
    except Exception:
        logger.exception('Failed to send password reset link email')
        messages.error(request, ' We could not send the reset link right now. Please try again later.')
        return redirect('forgot_password')

    messages.success(request, ' Reset link sent successfully. Please check your email.')
    return redirect(f'/reset_password/?email={user.email}')

def settings(request):
    if not request.session.has_key('is_logged'):
        return redirect('/home')

    user = User.objects.get(id=request.session['user_id'])
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'profession': 'Other', 'Savings': 0, 'income': 0},
    )

    if request.method == 'POST':
        user.first_name = request.POST.get('fname', user.first_name).strip()
        user.last_name = request.POST.get('lname', user.last_name).strip()
        email = request.POST.get('email', user.email).strip().lower()
        if email:
            user.email = email
            user.username = email
        user.save()

        # profile core fields
        profile.profession = request.POST.get('profession', profile.profession)
        profile.Savings = request.POST.get('Savings') or profile.Savings or 0
        profile.income = request.POST.get('income') or profile.income or 0
        # UI settings
        profile.currency = request.POST.get('currency', profile.currency)
        profile.dark_mode = True if request.POST.get('dark_mode') in ['on','true','1'] else False
        # budget_limit: accept numeric or blank
        budget_raw = request.POST.get('budget_limit')
        if budget_raw:
            try:
                profile.budget_limit = int(budget_raw)
            except ValueError:
                profile.budget_limit = profile.budget_limit
        profile.notifications_enabled = True if request.POST.get('notifications_enabled') in ['on','true','1'] else False
        profile.reminders_time = request.POST.get('reminders_time', profile.reminders_time)
        # normalize categories (comma separated)
        cats = request.POST.get('categories')
        if cats is not None:
            # remove extra spaces and empty items
            profile.categories = ','.join([c.strip() for c in cats.split(',') if c.strip()])
        profile.pin_enabled = True if request.POST.get('pin_enabled') in ['on','true','1'] else False
        profile.biometric_enabled = True if request.POST.get('biometric_enabled') in ['on','true','1'] else False
        profile.backup_enabled = True if request.POST.get('backup_enabled') in ['on','true','1'] else False
        if request.FILES.get('image'):
            profile.image = request.FILES['image']
        profile.save()

        messages.success(request, ' Settings updated successfully.')
        return redirect('settings')

    login_history = LoginHistory.objects.filter(user=user)
    current_login = login_history.first()
    return render(request, 'settings.html', {
        'user': user,
        'profile': profile,
        'login_history_count': login_history.count(),
        'current_login': current_login,
    })


def login_history(request):
    if not request.session.has_key('is_logged'):
        return redirect('/home')

    user = User.objects.get(id=request.session['user_id'])
    login_records = LoginHistory.objects.filter(user=user)
    return render(request, 'login_history.html', {
        'user': user,
        'login_records': login_records,
        'current_login': login_records.first(),
    })


def export_expenses_csv(request):
    if not request.session.has_key('is_logged'):
        return redirect('home')
    user = User.objects.get(id=request.session['user_id'])
    qs = Addmoney_info.objects.filter(user=user).order_by('-Date')
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expenses_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['id', 'type', 'amount', 'category', 'date'])
    for item in qs:
        writer.writerow([item.id, item.add_money, item.quantity, item.Category, item.Date])
    return response
def password(request):
    return render(request,'password.html')
def activity(request):
    return render(request,'activity.html')
def notepad(request):
    if not request.session.has_key('is_logged'):
        return redirect('home')
    user = User.objects.get(id=request.session['user_id'])
    history_id = request.GET.get('history_id')
    initial_content = ''
    if history_id:
        history_item = ToolHistory.objects.filter(user=user, tool_type='notepad', id=history_id).first()
        if history_item:
            initial_content = history_item.content
    return render(request,'notepad.html', {'user': user, 'initial_content': initial_content, 'history_id': history_id})
def paint(request):
    if not request.session.has_key('is_logged'):
        return redirect('home')
    user = User.objects.get(id=request.session['user_id'])
    history_id = request.GET.get('history_id')
    initial_image_url = ''
    if history_id:
        history_item = ToolHistory.objects.filter(user=user, tool_type='paint', id=history_id).first()
        if history_item and history_item.image:
            initial_image_url = history_item.image.url
    return render(request,'paint.html', {'user': user, 'initial_image_url': initial_image_url, 'history_id': history_id})
def layout2(request):
    return render(request,'layout2.html')
def layout3(request):
    return render(request,'layout3.html')
def page1(request):
    return render(request,'paint.html')
def page2(request):
    return render(request,'notepad.html')
def charts(request):
    return render(request,'charts.html')
def search(request):
    if request.session.has_key('is_logged'):
        user_id = request.session["user_id"]
        user = User.objects.get(id=user_id)
        fromdate = request.GET['fromdate']
        todate = request.GET['todate']
        addmoney = Addmoney_info.objects.filter(user=user, Date__range=[fromdate,todate]).order_by('-Date')
        return render(request,'tables.html',{'addmoney':addmoney})
    return redirect('home')
def tables(request):
    if request.session.has_key('is_logged'):
        user_id = request.session["user_id"]
        user = User.objects.get(id=user_id)
        fromdate = request.POST.get('fromdate') or request.GET.get('fromdate')
        todate = request.POST.get('todate') or request.GET.get('todate')
        addmoney = Addmoney_info.objects.filter(user=user)
        if fromdate and todate:
            addmoney = addmoney.filter(Date__range=[fromdate, todate])
        addmoney = addmoney.order_by('-Date')
        tool_history = ToolHistory.objects.filter(user=user)
        if fromdate and todate:
            tool_history = tool_history.filter(created_at__date__range=[fromdate, todate])
        tool_history = tool_history.order_by('-created_at')
        notepad_history = [item for item in tool_history if item.tool_type == 'notepad']
        paint_history = [item for item in tool_history if item.tool_type == 'paint']
        combined_history = []
        for item in addmoney:
            created_at = timezone.make_aware(datetime.datetime.combine(item.Date, datetime.time.min))
            combined_history.append({
                'kind': 'finance',
                'label': item.add_money,
                'title': item.Category,
                'amount': item.quantity,
                'date': created_at,
                'display_date': item.Date,
                'edit_url': f'/expense_edit/{item.id}',
                'delete_url': f'/expense_delete/{item.id}',
            })
        for item in tool_history:
            combined_history.append({
                'kind': 'tool',
                'label': item.get_tool_type_display(),
                'title': item.title,
                'amount': '',
                'date': item.created_at,
                'display_date': item.created_at,
                'tool_type': item.tool_type,
                'content': item.content,
                'image': item.image.url if item.image else '',
            })
        combined_history = sorted(combined_history, key=lambda entry: entry['date'], reverse=True)
        return render(request, 'tables.html', {
            'addmoney': addmoney,
            'finance_history': addmoney,
            'notepad_history': notepad_history,
            'paint_history': paint_history,
            'history_records': combined_history,
            'history_count': len(combined_history),
            'finance_count': addmoney.count(),
            'notepad_count': len(notepad_history),
            'paint_count': len(paint_history),
            'fromdate': fromdate,
            'todate': todate,
            'user': user,
        })
    return redirect('home')


def save_notepad(request):
    if not request.session.has_key('is_logged'):
        return redirect('home')
    user = User.objects.get(id=request.session['user_id'])
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            ToolHistory.objects.create(
                user=user,
                tool_type='notepad',
                title='Notepad note',
                content=content,
            )
            messages.success(request, 'Note saved to history.')
        else:
            messages.error(request, 'Please write something before saving.')
    return redirect('notepad')


def save_paint(request):
    if not request.session.has_key('is_logged'):
        return redirect('home')
    user = User.objects.get(id=request.session['user_id'])
    if request.method == 'POST':
        image_data = request.POST.get('image_data', '')
        if image_data.startswith('data:image/'):
            from django.core.files.base import ContentFile
            from base64 import b64decode
            header, encoded = image_data.split(',', 1)
            file_ext = 'png'
            content = ContentFile(b64decode(encoded), name=f'paint_{timezone.now().strftime("%Y%m%d_%H%M%S")}.{file_ext}')
            ToolHistory.objects.create(
                user=user,
                tool_type='paint',
                title='Paint sketch',
                image=content,
            )
            messages.success(request, 'Drawing saved to history.')
        else:
            messages.error(request, 'No drawing data found.')
    return redirect('paint')


def tool_history_delete(request, id):
    if not request.session.has_key('is_logged'):
        return redirect('/home')

    user_id = request.session.get('user_id')
    history_item = ToolHistory.objects.filter(id=id, user_id=user_id).first()
    if history_item:
        if history_item.image:
            history_item.image.delete(save=False)
        history_item.delete()
        messages.success(request, 'History item deleted permanently.')
    else:
        messages.error(request, 'History item not found.')
    return redirect('tables')

def addmoney(request):
    if request.session.has_key('is_logged'):
        user = User.objects.get(id=request.session["user_id"])
        return render(request,'addmoney.html',{'user': user})
    return redirect('/home')

def profile(request):
    if request.session.has_key('is_logged'):
        user = User.objects.get(id=request.session["user_id"])
        profile = getattr(user, 'userprofile', None)
        return render(request,'profile.html',{'user': user, 'profile': profile})
    return redirect('/home')

def profile_edit(request,id):
    if request.session.has_key('is_logged'):
        user = User.objects.get(id=id)
        profile = getattr(user, 'userprofile', None)
        return render(request, 'profile_edit.html', {'user': user, 'profile': profile})
    return redirect("/home")

def profile_update(request,id):
    if request.session.has_key('is_logged'):
        if request.method == "POST":
            user = User.objects.get(id=id)
            user.first_name = request.POST["fname"]
            user.last_name = request.POST["lname"]
            user.email = request.POST["email"]
            user.userprofile.Savings = request.POST["Savings"]
            user.userprofile.income = request.POST["income"]
            user.userprofile.profession = request.POST["profession"]
            # handle optional uploaded profile image
            if request.FILES.get('image'):
                user.userprofile.image = request.FILES['image']
            # also allow settings updates from profile edit form
            user.userprofile.currency = request.POST.get('currency', user.userprofile.currency)
            user.userprofile.dark_mode = bool(request.POST.get('dark_mode'))
            user.userprofile.budget_limit = request.POST.get('budget_limit') or user.userprofile.budget_limit
            user.userprofile.notifications_enabled = bool(request.POST.get('notifications_enabled'))
            user.userprofile.categories = request.POST.get('categories', user.userprofile.categories)
            user.userprofile.save()
            user.save()
            return redirect("/profile")
    return redirect("/home")   

def handleSignup(request):
    if request.method =='POST':
            # get the post parameters
            fname=request.POST["fname"]
            lname=request.POST["lname"]
            email = request.POST["email"]
            profession = request.POST['profession']
            Savings = request.POST['Savings']
            income = request.POST['income']
            pass1 = request.POST["pass1"]
            pass2 = request.POST["pass2"]
            profile = UserProfile(Savings = Savings,profession=profession,income=income)
            # check for errors in input
            email = email.strip().lower()
            if not email.endswith('@gmail.com'):
                messages.error(request, " Please use a Gmail address ending with @gmail.com")
                return redirect("/register")

            if len(pass1) < 8:
                messages.error(request, " Password must be at least 8 characters long")
                return redirect("/register")

            if pass1 != pass2:
                messages.error(request," Password do not match, Please try again")
                return redirect("/register")

            if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
                messages.error(request, " This mail is already registered. Please login instead.")
                return redirect("/login")
            
            # create the user
            user = User.objects.create_user(email, email, pass1)
            user.first_name=fname
            user.last_name=lname
            user.email = email
            # profile = UserProfile.objects.all()

            user.save()
            # p1=profile.save(commit=False)
            profile.user = user
            profile.save()
            messages.success(request," Your account has been successfully created")
            return redirect('login')
    else:
        return HttpResponse('404 - NOT FOUND ')
    return redirect('/login')

def handlelogin(request):
    if request.method =='POST':
        # get the post parameters
        loginemail = request.POST["loginemail"].strip().lower()
        loginpassword1=request.POST["loginpassword1"]
        try:
            user_obj = User.objects.get(email=loginemail)
        except User.DoesNotExist:
            messages.error(request," Invalid mail not registered. Please register first.")
            return redirect('register')

        user = authenticate(username=user_obj.username, password=loginpassword1)
        if user is not None:
            dj_login(request, user)
            request.session['is_logged'] = True
            user = request.user.id 
            request.session['user_id'] = user
            LoginHistory.objects.create(
                user=request.user,
                ip_address=_get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            messages.success(request, " Successfully logged in")
            return redirect('/index')
        else:
            messages.error(request," Invalid password. Please try again")  
            return redirect('login')  
    return HttpResponse('404-not found')
def handleLogout(request):
        del request.session['is_logged']
        del request.session["user_id"] 
        logout(request)
        messages.success(request, " Successfully logged out")
        return redirect('home')

def submit_query(request):
    if request.method != 'POST':
        return redirect('home')

    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    subject = request.POST.get('subject', '').strip() or 'ExpenseTracker landing page query'
    message = request.POST.get('message', '').strip()

    if not name or not email or not message:
        messages.error(request, 'Please fill in your name, email, and message before submitting the form.')
        return redirect('home')

    body = (
        'New query submitted from the ExpenseTracker landing page.\n\n'
        f'Name: {name}\n'
        f'Email: {email}\n'
        f'Subject: {subject}\n\n'
        f'Message:\n{message}'
    )

    try:
        sender_email = django_settings.EMAIL_HOST_USER or django_settings.DEFAULT_FROM_EMAIL or 'noreply@expensetracker.local'
        connection = get_connection(fail_silently=False)
        email_message = EmailMessage(
            subject=f'ExpenseTracker query: {subject}',
            body=body,
            from_email=sender_email,
            to=['angothuadhisheshu@gmail.com'],
            reply_to=[email],
            connection=connection,
        )
        email_message.send(fail_silently=False)
        messages.success(request, 'Your query has been sent successfully.')
    except Exception as error:
        logger.exception('Failed to send landing page query email')
        messages.error(request, 'We could not send your query right now. Please email angothuadhisheshu@gmail.com directly.')

    return redirect('home')

#add money form
def addmoney_submission(request):
    if request.session.has_key('is_logged'):
        if request.method == "POST":
            user_id = request.session["user_id"]
            user1 = User.objects.get(id=user_id)
            addmoney_info1 = Addmoney_info.objects.filter(user=user1).order_by('-Date')
            add_money = request.POST["add_money"]
            quantity = request.POST["quantity"]
            Date = request.POST["Date"]
            Category = request.POST["Category"]
            add = Addmoney_info(user = user1,add_money=add_money,quantity=quantity,Date = Date,Category= Category)
            add.save()
            paginator = Paginator(addmoney_info1, 4)
            page_number = request.GET.get('page')
            page_obj = Paginator.get_page(paginator,page_number)
            context = {
                'page_obj' : page_obj
                }
            return render(request,'index.html',context)
    return redirect('/index')
def addmoney_update(request,id):
    if request.session.has_key('is_logged'):
        if request.method == "POST":
            add  = Addmoney_info.objects.get(id=id)
            add .add_money = request.POST["add_money"]
            add.quantity = request.POST["quantity"]
            add.Date = request.POST["Date"]
            add.Category = request.POST["Category"]
            add .save()
            return redirect("/index")
    return redirect("/home")        

def expense_edit(request,id):
    if request.session.has_key('is_logged'):
        try:
            addmoney_info = Addmoney_info.objects.get(id=id)
        except Addmoney_info.DoesNotExist:
            messages.error(request, 'Requested entry not found.')
            return redirect('addmoney')
        user_id = request.session["user_id"]
        user1 = User.objects.get(id=user_id)
        categories = ['Food','Travel','Shopping','Necessities','Entertainment','Others']
        return render(request,'expense_edit.html',{'addmoney_info':addmoney_info,'categories':categories})
    return redirect("/home")  

def expense_edit_latest(request):
    """Render the most recent Addmoney_info for the logged-in user at /expense_edit/."""
    if not request.session.has_key('is_logged'):
        return redirect('/home')

    user_id = request.session.get('user_id')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('/home')

    addmoney_info = Addmoney_info.objects.filter(user=user).order_by('-Date').first()
    if not addmoney_info:
        # No entries yet — redirect to addmoney page with a message
        messages.info(request, 'No entries found. Create a new entry first.')
        return redirect('addmoney')

    categories = ['Food','Travel','Shopping','Necessities','Entertainment','Others']
    return render(request, 'expense_edit.html', {'addmoney_info': addmoney_info, 'categories': categories})

def expense_delete(request,id):
    if request.session.has_key('is_logged'):
        addmoney_info = Addmoney_info.objects.get(id=id)
        addmoney_info.delete()
        return redirect("/index")
    return redirect("/home")  

def expense_month(request):
    todays_date = datetime.date.today()
    one_month_ago = todays_date-datetime.timedelta(days=30)
    user_id = request.session["user_id"]
    user1 = User.objects.get(id=user_id)
    addmoney = Addmoney_info.objects.filter(user = user1,Date__gte=one_month_ago,Date__lte=todays_date)
    finalrep ={}

    def get_Category(addmoney_info):
        # if addmoney_info.add_money=="Expense":
        return addmoney_info.Category    
    Category_list = list(set(map(get_Category,addmoney)))

    def get_expense_category_amount(Category,add_money):
        quantity = 0 
        filtered_by_category = addmoney.filter(Category = Category,add_money="Expense") 
        for item in filtered_by_category:
            quantity+=item.quantity
        return quantity

    for x in addmoney:
        for y in Category_list:
            finalrep[y]= get_expense_category_amount(y,"Expense")

    return JsonResponse({'expense_category_data': finalrep}, safe=False)


def stats(request):
    if request.session.has_key('is_logged') :
        user_id = request.session["user_id"]
        user1 = User.objects.get(id=user_id)
        user_profile = getattr(user1, 'userprofile', None)
        report = _period_report(user1, 30)
        if report['current_expense'] > report['savings_value']:
            messages.warning(request, 'Your expenses exceeded your savings')
        context = {
            'addmoney': type('obj', (), report),
            'user': user1,
            'profile': user_profile,
            'report': report,
            'chart_labels_json': json.dumps(report['chart_categories']),
            'chart_values_json': json.dumps(report['chart_category_values']),
            'comparison_labels_json': json.dumps(['Current month', 'Previous month']),
            'comparison_income_json': json.dumps([report['current_income'], report['previous_income']]),
            'comparison_expense_json': json.dumps([report['current_expense'], report['previous_expense']]),
            'line_labels_json': json.dumps(report['chart_daily_labels']),
            'line_income_json': json.dumps(report['chart_daily_income']),
            'line_expense_json': json.dumps(report['chart_daily_expense']),
        }
        return render(request,'stats.html',context)
    return redirect('home')

def expense_week(request):
    todays_date = datetime.date.today()
    one_week_ago = todays_date-datetime.timedelta(days=7)
    user_id = request.session["user_id"]
    user1 = User.objects.get(id=user_id)
    addmoney = Addmoney_info.objects.filter(user = user1,Date__gte=one_week_ago,Date__lte=todays_date)
    finalrep ={}

    def get_Category(addmoney_info):
        return addmoney_info.Category
    Category_list = list(set(map(get_Category,addmoney)))


    def get_expense_category_amount(Category,add_money):
        quantity = 0 
        filtered_by_category = addmoney.filter(Category = Category,add_money="Expense") 
        for item in filtered_by_category:
            quantity+=item.quantity
        return quantity

    for x in addmoney:
        for y in Category_list:
            finalrep[y]= get_expense_category_amount(y,"Expense")

    return JsonResponse({'expense_category_data': finalrep}, safe=False)
    
def weekly(request):
    if request.session.has_key('is_logged') :
        user_id = request.session["user_id"]
        user1 = User.objects.get(id=user_id)
        user_profile = getattr(user1, 'userprofile', None)
        report = _period_report(user1, 7)
        if report['current_expense'] > report['savings_value']:
            messages.warning(request, 'Your expenses exceeded your savings')
        context = {
            'addmoney_info': type('obj', (), report),
            'user': user1,
            'profile': user_profile,
            'report': report,
            'chart_labels_json': json.dumps(report['chart_daily_labels']),
            'chart_income_json': json.dumps(report['chart_daily_income']),
            'chart_expense_json': json.dumps(report['chart_daily_expense']),
            'comparison_labels_json': json.dumps(['Current week', 'Previous week']),
            'comparison_income_json': json.dumps([report['current_income'], report['previous_income']]),
            'comparison_expense_json': json.dumps([report['current_expense'], report['previous_expense']]),
            'pie_labels_json': json.dumps(report['chart_categories']),
            'pie_values_json': json.dumps(report['chart_category_values']),
        }
        return render(request,'weekly.html', context)
    return redirect('home')

def check(request):
    if request.method == 'POST':
        user_exists = User.objects.filter(email=request.POST['email'])
        messages.error(request,"Email not registered, TRY AGAIN!!!")
        return redirect("/reset_password")

def info_year(request):
    todays_date = datetime.date.today()
    one_week_ago = todays_date-datetime.timedelta(days=30*12)
    user_id = request.session["user_id"]
    user1 = User.objects.get(id=user_id)
    addmoney = Addmoney_info.objects.filter(user = user1,Date__gte=one_week_ago,Date__lte=todays_date)
    finalrep ={}

    def get_Category(addmoney_info):
        return addmoney_info.Category
    Category_list = list(set(map(get_Category,addmoney)))


    def get_expense_category_amount(Category,add_money):
        quantity = 0 
        filtered_by_category = addmoney.filter(Category = Category,add_money="Expense") 
        for item in filtered_by_category:
            quantity+=item.quantity
        return quantity

    for x in addmoney:
        for y in Category_list:
            finalrep[y]= get_expense_category_amount(y,"Expense")

    return JsonResponse({'expense_category_data': finalrep}, safe=False)

def info(request):
    if request.session.has_key('is_logged'):
        user_id = request.session['user_id']
        user = User.objects.get(id=user_id)
        user_profile = getattr(user, 'userprofile', None)
        today = datetime.date.today()
        current_year = today.year
        previous_year = current_year - 1
        current_start = datetime.date(current_year, 1, 1)
        previous_start = datetime.date(previous_year, 1, 1)
        previous_end = datetime.date(previous_year, 12, 31)
        current_records = Addmoney_info.objects.filter(user=user, Date__gte=current_start, Date__lte=today).order_by('Date')
        previous_records = Addmoney_info.objects.filter(user=user, Date__gte=previous_start, Date__lte=previous_end).order_by('Date')

        report = _period_report(user, 365)
        current_expense = sum(item.quantity for item in current_records if item.add_money == 'Expense')
        current_income = sum(item.quantity for item in current_records if item.add_money == 'Income')
        previous_expense = sum(item.quantity for item in previous_records if item.add_money == 'Expense')
        previous_income = sum(item.quantity for item in previous_records if item.add_money == 'Income')
        month_labels, year_income_series, year_expense_series = _monthly_series(current_records, current_year)
        prev_month_labels, prev_year_income_series, prev_year_expense_series = _monthly_series(previous_records, previous_year)
        savings_value = getattr(user_profile, 'Savings', 0) or 0
        balance_total = savings_value + current_income - current_expense
        balance_left = max(balance_total, 0)
        deficit = abs(balance_total) if balance_total < 0 else 0

        category_totals = {}
        for category in REPORT_CATEGORIES:
            category_totals[category] = sum(item.quantity for item in current_records if item.Category == category and item.add_money == 'Expense')

        income_change_percent = 100 if previous_income == 0 and current_income > 0 else (0 if previous_income == 0 else round(((current_income - previous_income) / previous_income) * 100, 1))
        expense_change_percent = 100 if previous_expense == 0 and current_expense > 0 else (0 if previous_expense == 0 else round(((current_expense - previous_expense) / previous_expense) * 100, 1))

        report = {
            'current': current_records,
            'previous': previous_records,
            'current_expense': current_expense,
            'current_income': current_income,
            'previous_expense': previous_expense,
            'previous_income': previous_income,
            'compare_income_diff': current_income - previous_income,
            'compare_expense_diff': current_expense - previous_expense,
            'income_change_percent': income_change_percent,
            'expense_change_percent': expense_change_percent,
            'balance_left': balance_left,
            'deficit': deficit,
            'savings_value': savings_value,
            'category_totals': category_totals,
            'chart_categories': [category for category, total in category_totals.items() if total > 0],
            'chart_category_values': [total for total in category_totals.values() if total > 0],
            'chart_daily_labels': month_labels,
            'chart_daily_income': year_income_series,
            'chart_daily_expense': year_expense_series,
            'highest_expense': _transaction_extreme(current_records, 'Expense', 'max'),
            'lowest_expense': _transaction_extreme(current_records, 'Expense', 'min'),
            'highest_income': _transaction_extreme(current_records, 'Income', 'max'),
            'lowest_income': _transaction_extreme(current_records, 'Income', 'min'),
            'previous_total': previous_expense + previous_income,
            'current_total': current_expense + current_income,
            'transaction_count': current_records.count(),
            'sum': current_expense,
            'sum1': current_income,
            'x': balance_left,
            'y': deficit,
            'expense_category_data': category_totals,
            'current_balance': balance_left,
            'budget_used': round((current_expense / savings_value) * 100, 1) if savings_value else 0,
        }
        context = {
            'addmoney': type('obj', (), report),
            'user': user,
            'profile': user_profile,
            'report': report,
            'chart_labels_json': json.dumps(report['chart_categories']),
            'chart_values_json': json.dumps(report['chart_category_values']),
            'comparison_labels_json': json.dumps(['Current year', 'Previous year']),
            'comparison_income_json': json.dumps([report['current_income'], report['previous_income']]),
            'comparison_expense_json': json.dumps([report['current_expense'], report['previous_expense']]),
            'year_month_labels_json': json.dumps(month_labels),
            'year_month_income_json': json.dumps(year_income_series),
            'year_month_expense_json': json.dumps(year_expense_series),
            'year_prev_month_labels_json': json.dumps(prev_month_labels),
            'year_prev_month_income_json': json.dumps(prev_year_income_series),
            'year_prev_month_expense_json': json.dumps(prev_year_expense_series),
            'year_compare_labels_json': json.dumps([str(current_year), str(previous_year)]),
            'year_compare_income_json': json.dumps([report['current_income'], previous_income]),
            'year_compare_expense_json': json.dumps([report['current_expense'], previous_expense]),
        }
        return render(request, 'info.html', context)
    return redirect('home')
