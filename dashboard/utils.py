from django.apps import apps
from dashboard.models import FormControl

def generate_form_controls(model_name, form_label):
    model = apps.get_model('dashboard', model_name) 

    for field in model._meta.get_fields():
        if field.concrete and not field.auto_created:
            FormControl.objects.get_or_create(
                form=form_label,
                name=field.name,
                defaults={'required': True, 'status': True}
            )
