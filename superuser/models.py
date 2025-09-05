from ckeditor_uploader.fields import RichTextUploadingField
from django.db import models

# Create your models here.


class StaticPages(models.Model):
    title = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    body_content = RichTextUploadingField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    alert_users = models.BooleanField(default=False,
                                      help_text="Check it to alert users | work for only Terms and Policies pages")

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.title}"

    class Meta:
        verbose_name = verbose_name_plural = "Static Pages"
