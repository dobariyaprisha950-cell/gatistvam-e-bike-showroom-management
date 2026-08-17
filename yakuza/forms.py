from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany,
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, ExpenseMaster, Expense, InvoiceSetting, Settings
)


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = '__all__'


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['role', 'branch', 'mobile_number', 'is_active', 'profile_photo']


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = '__all__'


class VehicleCompanyForm(forms.ModelForm):
    class Meta:
        model = VehicleCompany
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
        fields = ['company', 'model', 'color', 'quantity', 'purchase_price']


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


class ProfileUpdateForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150, required=True)
    username = forms.CharField(max_length=150, required=True)
    mobile = forms.CharField(max_length=15, required=False)
    profile_photo = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ['username']

class BranchSettingsForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['branch_name', 'owner_name', 'address', 'gst_number', 'phone', 'logo']

class InvoiceSettingsForm(forms.ModelForm):
    class Meta:
        model = InvoiceSetting
        fields = ['company_name', 'invoice_prefix', 'company_address', 'gstin', 'phone', 'terms', 'logo']

class SystemUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(), required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name']