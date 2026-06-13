from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import views

urlpatterns = [
    path("auth/login/", obtain_auth_token, name="auth-login"),
    path("categories/", views.category_list, name="category-list"),
    path("expenses/", views.expense_list, name="expense-list"),
    path("expenses/summary/", views.expense_summary, name="expense-summary"),
    path("expenses/monthly-summary/", views.monthly_summary, name="monthly-summary"),
    path("expenses/<pk>/", views.expense_detail, name="expense-detail"),
]
