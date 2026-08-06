from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'yakuza'

router = DefaultRouter()
router.register(r'branches', views.BranchViewSet)
router.register(r'profiles', views.UserProfileViewSet)
router.register(r'suppliers', views.SupplierViewSet)
router.register(r'vehicle-companies', views.VehicleCompanyViewSet)
router.register(r'battery-capacities', views.BatteryCapacityViewSet)
router.register(r'vehicle-colors', views.VehicleColorViewSet)
router.register(r'vehicle-models', views.VehicleModelViewSet)
router.register(r'purchases', views.PurchaseViewSet, basename='purchase')
router.register(r'stocks', views.StockViewSet, basename='stock')
router.register(r'sales', views.SalesViewSet, basename='sales')
router.register(r'customers', views.CustomerViewSet)
router.register(r'expense-masters', views.ExpenseMasterViewSet)
router.register(r'expenses', views.ExpenseViewSet, basename='expense')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'settings', views.SettingsViewSet)
router.register(r'audit-logs', views.AuditLogViewSet)

urlpatterns = [
    # Frontend Pages
    path('accounts/login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    path('live_stock/', views.live_stock, name='live_stock'),

    path('purchase/', views.purchase_page_view, name='purchase'),
    path('ajax/add-supplier/', views.add_supplier_ajax, name='add_supplier_ajax'),
    path('ajax/add-company/', views.add_company_ajax, name='add_company_ajax'),
    path('ajax/add-model/', views.add_model_ajax, name='add_model_ajax'),
    path('ajax/add-color/', views.add_color_ajax, name='add_color_ajax'),

    path('purchase_history/', views.purchase_history, name='purchase_history'),
    path('sales/', views.sales, name='sales'),
    path('customer/', views.customer, name='customer'),
    path('expenses/', views.expenses, name='expenses'),
    path('expenses/edit/<int:pk>/', views.edit_expense, name='edit_expense'),
    path('expenses/delete/<int:pk>/', views.delete_expense, name='delete_expense'),
    path('reports/', views.reports, name='reports'),
    path('notifications/', views.notifications, name='notifications'),
    path('settings/', views.settings, name='settings'),
   
    # REST APIs
    path('api/', include(router.urls)),
    path('reports/profit/', views.ProfitReportView.as_view(), name='profit-report'),
]