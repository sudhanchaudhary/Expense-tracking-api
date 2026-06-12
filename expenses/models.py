from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='category',null=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "categories"
        unique_together = ("user", "name")

    def __str__(self):
        return self.name


class Expense(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='expense',null=True)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3,default="USD",help_text="ISO 4217 currency code (e.g., USD, EUR, GBP)",null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="expenses")
    date = models.DateField()
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title} ({self.amount} {self.currency})"
