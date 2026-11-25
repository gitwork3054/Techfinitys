from django.urls import path
from . import views, operations, projects_plus, collaboration, google_signin, billing, activity_center, task_collab, push_notifications, zoho_import
urlpatterns=[
 path('api/zoho/status/', zoho_import.status, name='zoho_import_status'),
 path('api/zoho/connect/', zoho_import.connect, name='zoho_import_connect'),
 path('api/zoho/callback/', zoho_import.callback, name='zoho_import_callback'),
 path('api/zoho/portals/', zoho_import.portals, name='zoho_import_portals'),
 path('api/zoho/preview/', zoho_import.preview, name='zoho_import_preview'),
 path('api/zoho/import/', zoho_import.import_projects, name='zoho_import_projects'),
 path('api/zoho/disconnect/', zoho_import.disconnect, name='zoho_import_disconnect'),

 path('sw.js',push_notifications.service_worker,name='push_worker'),
 path('api/push/config/',push_notifications.push_config,name='push_config'),
 path('api/push/subscription/',push_notifications.push_subscription,name='push_subscription'),
 path('api/push/status/',push_notifications.push_status,name='push_status'),
 path('api/push/test/',push_notifications.push_test,name='push_test'),

 path('api/admin-activity/',activity_center.admin_activity_api,name='admin_activity_api'),
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
 path('api/task-detail/<uuid:task_id>/',task_collab.task_detail_api,name='task_detail_api'),
 path('api/projects-plus/upload/',projects_plus.document_upload,name='project_document_upload'),
 path('api/projects-plus/feed-photo/upload/',projects_plus.project_feed_photo_upload,name='project_feed_photo_upload'),
 path('api/projects-plus/feed-photo/<uuid:post_id>/',projects_plus.project_feed_photo,name='project_feed_photo'),
 path('api/projects-plus/document/<uuid:document_id>/',projects_plus.document_download,name='project_document_download'),
 path('api/project-export/<str:kind>/',projects_plus.export_project_csv,name='project_csv'),
 path('',views.dashboard,name='dashboard'),path('login/',views.login_view,name='login'),path('logout/',views.logout_view,name='logout'),
 path('api/workspace/',views.workspace_api,name='workspace_api'),path('api/operations/',operations.operations_api,name='operations_api'),path('api/export/<str:kind>/',operations.export_csv,name='export_csv'),path('api/file/<str:record_id>/',views.file_download,name='file_download'),path('api/razorpay/',views.razorpay_stub,name='razorpay_stub')
]
