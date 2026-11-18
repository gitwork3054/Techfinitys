from django.urls import path
from . import views, operations
urlpatterns=[
 path('',views.dashboard,name='dashboard'),path('login/',views.login_view,name='login'),path('logout/',views.logout_view,name='logout'),
 path('api/workspace/',views.workspace_api,name='workspace_api'),path('api/operations/',operations.operations_api,name='operations_api'),path('api/export/<str:kind>/',operations.export_csv,name='export_csv'),path('api/file/<str:record_id>/',views.file_download,name='file_download'),path('api/razorpay/',views.razorpay_stub,name='razorpay_stub')
]
