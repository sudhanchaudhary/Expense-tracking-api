from rest_framework import status
from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from django.db.models import Sum
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.db.models import Q

from .models import Category, Expense
from .serializers import CategorySerializer, ExpenseSerializer
from .exchange_rates import convert_amount
from .bot_alerts import check_budget_alert

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def category_list(request):
    if request.method == "GET":
        categories = Category.objects.filter(user=request.user)
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    serializer = CategorySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def expense_list(request):
    if request.method == "GET":
        expenses = Expense.objects.filter(user=request.user)
        search = request.query_params.get("search")
        if search:
            expenses = expenses.filter(
                Q(title__icontains=search) | Q(notes__icontains=search)
            )
            print(f"Filtered by search: '{search}'")
        min_amount = request.query_params.get("min_amount")
        max_amount = request.query_params.get("max_amount")
        if min_amount:
            expenses = expenses.filter(amount__gte=min_amount)
            print(f"Filtered by min_amount: {min_amount}")
        if max_amount:
            expenses = expenses.filter(amount__lte=max_amount)
            print(f"Filtered by max_amount: {max_amount}")
        category = request.query_params.get("category")
        if category:
            expenses = expenses.filter(category=category)
            print(f"Filtered by category: {category}")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            expenses = expenses.filter(date__gte=start_date)
            print(f"Filtered by start_date: {start_date}")
        if end_date:
            expenses = expenses.filter(date__lte=end_date)
            print(f"Filtered by end_date: {end_date}")
        expenses = expenses.order_by("-date")
        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)
    serializer = ExpenseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    expense = serializer.save(user=request.user)
    check_budget_alert(expense.category, request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def expense_detail(request, pk):
    try:
        expense = Expense.objects.get(pk=pk, user=request.user)
    except Expense.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        serializer = ExpenseSerializer(expense)
        return Response(serializer.data)
    if request.method == "PUT":
        serializer = ExpenseSerializer(expense, data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = serializer.save()
        check_budget_alert(expense.category, request.user)
        return Response(serializer.data)
    if request.method == "DELETE":
        expense.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def expense_summary(request):
    base_currency = getattr(settings, "BASE_CURRENCY", "USD")
    expenses = (
        Expense.objects
        .filter(user=request.user)
        .select_related("category")
        .order_by("category__name")
    )
    categories_dict = {}
    for expense in expenses:
        cat_name = expense.category.name
        if cat_name not in categories_dict:
            categories_dict[cat_name] = []
        categories_dict[cat_name].append(expense)
    summary = []
    for cat_name, expenses_list in sorted(categories_dict.items()):
        category_total = Decimal("0.00")
        rate_info = None

        for expense in expenses_list:
            if expense.currency != base_currency:
                try:
                    conversion = convert_amount(
                        expense.amount,
                        expense.currency,
                        base_currency
                    )
                    category_total += Decimal(conversion["converted_amount"])
                    rate_info = {
                        "rate": conversion["rate"],
                        "date": conversion["date"]
                    }
                except Exception:
                    continue
            else:
                category_total += expense.amount
                if not rate_info:
                    rate_info = {
                        "rate": "1.00",
                        "date": datetime.now().date().isoformat()
                    }
        if category_total > 0:
            summary.append({
                "category": cat_name,
                "total": str(round(category_total, 2)),
                "rate": rate_info["rate"] if rate_info else "1.00",
                "as_of": rate_info["date"] if rate_info else datetime.now().date().isoformat()
            })

    return Response({
        "base_currency": base_currency,
        "categories": summary
    })
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_summary(request):
    expenses = (
        Expense.objects
        .filter(user=request.user)
        .select_related('category')
        .order_by('-date')
    )
    print(f"Found {expenses.count()} total expenses for user")
    monthly_data = {}
    for expense in expenses:
        month_key = expense.date.strftime("%Y-%m")
        print(f"  Processing: {expense.title} ({expense.date}) → month: {month_key}")
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                "month": month_key,
                "total": Decimal("0.00"),
                "count": 0,
                "categories": {}
            }
        monthly_data[month_key]["total"] += expense.amount
        monthly_data[month_key]["count"] += 1
        cat_name = expense.category.name
        if cat_name not in monthly_data[month_key]["categories"]:
            monthly_data[month_key]["categories"][cat_name] = Decimal("0.00")
        monthly_data[month_key]["categories"][cat_name] += expense.amount
    summary = []
    for month_key in sorted(monthly_data.keys(), reverse=True):
        month_info = monthly_data[month_key]
        categories_list = [
            {
                "category": cat,
                "total": str(round(amount, 2))
            }
            for cat, amount in sorted(month_info["categories"].items())
        ]
        summary.append({
            "month": month_info["month"],
            "total": str(round(month_info["total"], 2)),
            "count": month_info["count"],
            "categories": categories_list
        })
        
        print(f"Month {month_info['month']}: ${month_info['total']} ({month_info['count']} expenses)")
    
    return Response({"summary": summary})