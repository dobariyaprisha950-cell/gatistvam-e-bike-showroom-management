from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect


app_name = 'yakuza'

router = DefaultRouter()
router.register(r'branches', views.BranchViewSet)
router.register(r'profiles', views.UserProfileViewSet)
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'vehicle-colors', views.VehicleColorViewSet, basename='vehiclecolor')
router.register(r'vehicle-models', views.VehicleModelViewSet, basename='vehiclemodel')
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
    path('', lambda request: redirect('yakuza:login'), name='home'),
    # Branch Switcher
    path('service-worker.js', views.service_worker, name='service_worker'),
    path('switch-branch/', views.switch_branch, name='switch_branch'),
    
    # Frontend Pages
    path('accounts/login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/sales-chart/', views.get_sales_chart_data, name='sales_chart_api'),
    path('live_stock/', views.live_stock, name='live_stock'),

    # Purchase Module Endpoints
    path('purchase/', views.purchase_page_view, name='purchase'),
    path('ajax/add-supplier/', views.add_supplier_ajax, name='add_supplier_ajax'),
    path('ajax/add-company/', views.add_company_ajax, name='add_company_ajax'),
    path('ajax/add-model/', views.add_model_ajax, name='add_model_ajax'),
    path('ajax/add-color/', views.add_color_ajax, name='add_color_ajax'),
    path('purchase_history/', views.purchase_history, name='purchase_history'),

    # Sales & Customer Endpoints
    path('sales/', views.sales, name='sales'),
    path('ajax/sales/stock-options/', views.get_sales_stock_options_ajax, name='sales_stock_options'),
    path('sales/upload-pdf/<int:sale_id>/', views.upload_invoice_pdf, name='upload_invoice_pdf'),
    path('sales/whatsapp-share/<int:sale_id>/', views.save_and_share_whatsapp, name='save_and_share_whatsapp'),
    path('invoice/pdf/<int:sale_id>/', views.generate_invoice_pdf, name='generate_invoice_pdf'),
    path('customer/', views.customer, name='customer'),
    path('customer/invoice-data/<int:sale_id>/', views.get_customer_invoice_ajax, name='get_customer_invoice_ajax'),

    # Expense Module Endpoints
    path('expenses/', views.expenses, name='expenses'),
    path('expenses/edit/<int:pk>/', views.edit_expense, name='edit_expense'),
    path('expenses/delete/<int:pk>/', views.delete_expense, name='delete_expense'),

    # Reporting & Notifications
    path('reports/', views.reports, name='reports'),
    path('reports/pdf/', views.generate_reports_pdf, name='generate_reports_pdf'),
    path('notifications/', views.notifications, name='notifications'),
    
    # Settings & Admin Utilities
    path('settings/', views.settings, name='settings'),
    path('settings/update-profile/', views.update_profile_ajax, name='update_profile'),
    path('settings/update-branch/', views.update_branch_ajax, name='update_branch'),
    path('toggle-user-status/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('settings/save-user/', views.save_user_ajax, name='save_user_ajax'),
    
    path('settings/update-invoice/', views.update_invoice_ajax, name='update_invoice'),
    path('settings/update-notifications/', views.update_notifications_ajax, name='update_notifications'),
    
    path('settings/create-backup/', views.create_backup_ajax, name='create_backup'),
    path('settings/audit-log/export-csv/', views.export_audit_csv, name='export_audit_csv'),
    path('settings/audit-log/export-pdf/', views.export_audit_pdf, name='export_audit_pdf'),

    path('settings/restore-backup/', views.restore_backup, name='restore_backup'),
   
    path('settings/export-audit-logs/<str:fmt>/', views.export_audit_logs, name='export_audit_logs'),
    
    # REST APIs
    path('api/', include(router.urls)),
    path('reports/profit/', views.ProfitReportView.as_view(), name='profit-report'),
   
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)