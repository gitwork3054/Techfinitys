from django.urls import path
from . import views, operations, projects_plus
urlpatterns=[
 path('api/projects-plus/',projects_plus.projects_plus_api,name='projects_plus_api'),
 path('api/projects-plus/upload/',projects_plus.document_upload,name='project_document_upload'),
 path('api/projects-plus/document/<uuid:document_id>/',projects_plus.document_download,name='project_document_download'),
 path('api/project-export/<str:kind>/',projects_plus.export_project_csv,name='project_csv'),
 path('',views.dashboard,name='dashboard'),path('login/',views.login_view,name='login'),path('logout/',views.logout_view,name='logout'),
 path('api/workspace/',views.workspace_api,name='workspace_api'),path('api/operations/',operations.operations_api,name='operations_api'),path('api/export/<str:kind>/',operations.export_csv,name='export_csv'),path('api/file/<str:record_id>/',views.file_download,name='file_download'),path('api/razorpay/',views.razorpay_stub,name='razorpay_stub')
]
