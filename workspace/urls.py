from django.urls import path
from . import views, operations, projects_plus, collaboration, google_signin, billing
urlpatterns=[
 path('api/billing/', billing.billing_api, name='billing_api'),
 path('api/billing/pdf/<uuid:invoice_id>/', billing.invoice_pdf, name='billing_pdf'),
 path('api/billing/stamp/', billing.stamp_upload, name='billing_stamp'),
 path('api/billing/export/', billing.billing_export, name='billing_export'),
 path('auth/google/',google_signin.google_start,name='google_start'),
 path('auth/google/callback/',google_signin.google_callback,name='google_callback'),
 path('api/collaboration/',collaboration.collaboration_api,name='collaboration_api'),
 path('api/collaboration/thread/<uuid:conversation_id>/',collaboration.conversation_messages,name='conversation_messages'),
 path('api/collaboration/profile/',collaboration.own_profile,name='own_profile'),
 path('api/collaboration/avatar/<int:member_id>/',collaboration.avatar_file,name='avatar_file'),
 path('api/projects-plus/',projects_plus.projects_plus_api,name='projects_plus_api'),
 path('api/projects-plus/upload/',projects_plus.document_upload,name='project_document_upload'),
 path('api/projects-plus/document/<uuid:document_id>/',projects_plus.document_download,name='project_document_download'),
 path('api/project-export/<str:kind>/',projects_plus.export_project_csv,name='project_csv'),
 path('',views.dashboard,name='dashboard'),path('login/',views.login_view,name='login'),path('logout/',views.logout_view,name='logout'),
 path('api/workspace/',views.workspace_api,name='workspace_api'),path('api/operations/',operations.operations_api,name='operations_api'),path('api/export/<str:kind>/',operations.export_csv,name='export_csv'),path('api/file/<str:record_id>/',views.file_download,name='file_download'),path('api/razorpay/',views.razorpay_stub,name='razorpay_stub')
]
