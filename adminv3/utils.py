from django.http import QueryDict

from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib.auth.models import User
from django.core.signing import Signer, BadSignature
import base64
from django.utils import timezone

from datetime import date, datetime, timedelta

signer = Signer()


def requestParamsToDict(request, url_params=False, get_params=False, post_params=False):
    parsed_params = {}
    if url_params:
        current_url_params = request.META.get('HTTP_X_URL_PARAMETERS')
        if '?' in current_url_params:
            current_url_params = current_url_params.split('?')[-1]
            parsed_params = QueryDict(current_url_params)
    elif get_params:
        parsed_params = dict(request.GET.items())
    elif post_params:
        parsed_params = dict(request.POST.items())

    return parsed_params
