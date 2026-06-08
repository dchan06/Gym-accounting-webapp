from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload_statement, name='upload'),
    path('upload/<int:upload_id>/label/', views.label_statement, name='label_statement'),
    path('upload/<int:upload_id>/save/', views.save_labelled, name='save_labelled'),
    path('api/transaction/<int:transaction_id>/label/', views.api_set_label, name='api_set_label'),
    path('api/transaction/<int:transaction_id>/suggest/', views.api_suggest_labels, name='api_suggest_labels'),
    path('metrics/', views.metrics, name='metrics'),
    path('pl/', views.pl, name='pl'),
    path('agm/<str:month_str>/download/', views.download_agm_csv, name='download_agm'),
    path('labels/', views.labels_manage, name='labels'),
    path('api/transactions/', views.api_transactions, name='api_transactions'),
    path('hooks/n8n/', views.n8n_inbound_webhook, name='n8n_inbound_webhook'),
    path('api/pl/n8n-last/', views.n8n_webhook_last, name='n8n_webhook_last'),
]
