import requests
from django.conf import settings
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum
from .models import Expense



def send_discord_alert(message: str) -> bool:
    """
    Send alert message to Discord webhook.
    
    Args:
        message: The message to send
    
    Returns:
        True if successful, False if failed
    """
    webhook_url = getattr(settings, 'DISCORD_WEBHOOK_URL', '')
    
    # Check if webhook URL is configured
    if not webhook_url:
        print("  DISCORD_WEBHOOK_URL not configured in .env")
        return False
    
    try:
        # Discord webhook payload format
        payload = {
            "content": message,
            "embeds": [
                {
                    "color": 16711680,  # Red color (0xFF0000)
                    "title": " Budget Alert",
                    "description": message,
                    "footer": {
                        "text": f"Sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            ]
        }
        
        # Send webhook request
        response = requests.post(webhook_url, json=payload, timeout=5)
        
        # Discord returns 204 (No Content) for successful posts
        if response.status_code in [200, 204]:
            print(f"Discord alert sent successfully")
            return True
        else:
            print(f" Discord webhook failed: {response.status_code}")
            return False
    
    except Exception as e:
        print(f" Discord alert error: {e}")
        return False


def check_budget_alert(category, user) -> bool:
    """
    Check if category spending exceeds monthly limit.
    If yes, send Discord alert.
    
    Args:
        category: The Category object
        user: The User object
    
    Returns:
        True if alert was sent, False otherwise
    """
    
    # If no monthly limit set, skip
    if not category.monthly_limit:
        return False
    
    # Get current month (first day to today)
    today = datetime.now().date()
    month_start = today.replace(day=1)
    
    # Calculate month-to-date total for this category
    month_total = (
        Expense.objects
        .filter(
            user=user,
            category=category,
            date__gte=month_start,
            date__lte=today
        )
        .aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    )
    
    # Check if spending exceeds limit
    if month_total > category.monthly_limit:
        # Format month/year
        month_year = today.strftime("%B %Y")
        
        # Create alert message
        message = (
            f"Budget Alert: \"{category.name}\" is over its monthly limit!\n\n"
            f" **Spent:** ${month_total}\n"
            f"**Limit:** ${category.monthly_limit}\n"
            f"**Period:** {month_year}\n"
            f"**Over by:** ${month_total - category.monthly_limit}"
        )
        
        # Send Discord alert
        return send_discord_alert(message)
    
    return False