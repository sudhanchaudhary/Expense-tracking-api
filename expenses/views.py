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
    """
    GET: List all expenses with advanced filtering options
    
    Query Parameters (all optional):
    - ?search=keyword          → Search in title and notes (case-insensitive)
    - ?min_amount=10          → Minimum expense amount
    - ?max_amount=100         → Maximum expense amount
    - ?category=1             → Filter by category ID
    - ?start_date=2026-06-01  → Start date (inclusive)
    - ?end_date=2026-06-30    → End date (inclusive)
    
    Examples:
    GET /api/expenses/?search=hotel
    GET /api/expenses/?min_amount=50&max_amount=200
    GET /api/expenses/?category=1&start_date=2026-06-01
    GET /api/expenses/?search=restaurant&min_amount=20&max_amount=100&category=1
    
    POST: Create a new expense
    """
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
    """
    GET: Retrieve a specific expense by ID
    PUT: Update a specific expense
    DELETE: Delete a specific expense
    """
    
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