from django import forms
from django.core.exceptions import ValidationError
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany, BatteryCapacity,
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, ExpenseMaster, Expense 
)


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = '__all__'


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['role', 'branch', 'mobile_number', 'is_active']


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = '__all__'


class VehicleCompanyForm(forms.ModelForm):
    class Meta:
        model = VehicleCompany
        fields = '__all__'


class BatteryCapacityForm(forms.ModelForm):
    class Meta:
        model = BatteryCapacity
        fields = '__all__'


class VehicleColorForm(forms.ModelForm):
    class Meta:
        model = VehicleColor
        fields = '__all__'


class VehicleModelForm(forms.ModelForm):
    class Meta:
        model = VehicleModel
        fields = '__all__'


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ['purchase_date', 'supplier', 'branch', 'invoice_number', 'invoice_date', 'invoice_photo', 'remarks']
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'invoice_date': forms.DateInput(attrs={'type': 'date'}),
        }


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ['company', 'model', 'color', 'battery_capacity', 'quantity', 'purchase_price']


class SalesForm(forms.ModelForm):
    chassis_number = forms.CharField(max_length=100, required=True, label="Chassis Number")
    battery_number = forms.CharField(max_length=100, required=True, label="Battery Number")
    motor_number = forms.CharField(max_length=100, required=True, label="Motor Number")
    controller_number = forms.CharField(max_length=100, required=True, label="Controller Number")

    class Meta:
        model = Sales
        fields = [
            'invoice_date', 'customer_name', 'mobile_number', 'aadhar_number',
            'stock', 'selling_price', 'discount', 'payment_method'
        ]
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock and stock.stock_status != Stock.StockStatus.AVAILABLE:
            raise ValidationError("Selected vehicle stock is not available for sale.")
        return stock


class ExpenseMasterForm(forms.ModelForm):
    class Meta:
        model = ExpenseMaster
        fields = '__all__'


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['expense_master', 'branch', 'expense_date', 'amount', 'description']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
        }

