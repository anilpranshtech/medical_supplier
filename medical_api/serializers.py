from django.contrib.auth import get_user_model
from rest_framework import serializers, mixins, viewsets
from django.contrib.auth.models import User
import re

from rest_framework.permissions import IsAuthenticated

from dashboard.models import DoctorProfile
from django.db import IntegrityError


class UserLoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=255)

    class Meta:
        model = User
        fields = ['email', 'password']


class DoctorRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()

    # DoctorProfile fields
    current_position = serializers.CharField()
    workplace = serializers.CharField()
    nationality = serializers.CharField()
    residency = serializers.CharField()
    country_code = serializers.CharField()
    phone_number = serializers.CharField()
    specialty = serializers.CharField()

    class Meta:
        model = User
        fields = (
            'first_name', 'last_name', 'email', 'password', 'confirm_password',
            'current_position', 'workplace', 'nationality', 'residency',
            'country_code', 'phone_number', 'specialty'
        )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")

        password = data['password']

        # Password strength validations
        if len(password) < 8:
            raise serializers.ValidationError({"password": "Password must be at least 8 characters long."})
        if not re.search(r'[A-Z]', password):
            raise serializers.ValidationError({"password": "Password must contain at least one uppercase letter."})
        if not re.search(r'[a-z]', password):
            raise serializers.ValidationError({"password": "Password must contain at least one lowercase letter."})
        if not re.search(r'\d', password):
            raise serializers.ValidationError({"password": "Password must contain at least one number."})
        if not re.search(r'[@$!%*?&#^()_+=\[{\]};:<>|./~]', password):
            raise serializers.ValidationError({"password": "Password must contain at least one special character."})

        return data

    def generate_unique_username(self, base_username):
        from django.utils.text import slugify
        from django.utils.crypto import get_random_string

        base_username = slugify(base_username)
        username = base_username
        while User.objects.filter(username=username).exists():
            username = f"{base_username}-{get_random_string(4).lower()}"
        return username

    def create(self, validated_data):
        profile_fields = {
            'current_position': validated_data.pop('current_position'),
            'workplace': validated_data.pop('workplace'),
            'nationality': validated_data.pop('nationality'),
            'residency': validated_data.pop('residency'),
            'country_code': validated_data.pop('country_code'),
            'phone_number': validated_data.pop('phone_number'),
            'specialty': validated_data.pop('specialty'),
        }
        validated_data.pop('confirm_password')

        email = validated_data['email']
        validated_data['username'] = self.generate_unique_username(email.split('@')[0])

        try:
            user = User.objects.create_user(**validated_data)
            DoctorProfile.objects.create(user=user, **profile_fields)
        except IntegrityError:
            raise serializers.ValidationError("A user with this email already exists.")

        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_new_password = serializers.CharField(write_only=True)

    class Meta:
        model = get_user_model()

    def validate(self, data):
        user = self.context['user']

        if not user.check_password(data.get('old_password')):
            raise serializers.ValidationError({"old_password": "Old password is incorrect."})

        new_password = data.get('new_password')
        confirm_password = data.get('confirm_new_password')

        if new_password != confirm_password:
            raise serializers.ValidationError({"new_password": "New passwords do not match."})

        # Password complexity validation
        if not re.search(r'[A-Z]', new_password):
            raise serializers.ValidationError({"new_password": "Password must contain at least one uppercase letter."})
        if not re.search(r'[a-z]', new_password):
            raise serializers.ValidationError({"new_password": "Password must contain at least one lowercase letter."})
        if not re.search(r'\d', new_password):
            raise serializers.ValidationError({"new_password": "Password must contain at least one number."})
        if not re.search(r'[@$!%*?&#^()_+=\[{\]};:<>|./~]', new_password):
            raise serializers.ValidationError({"new_password": "Password must contain at least one special character."})
        if len(new_password) < 8:
            raise serializers.ValidationError({"new_password": "Password must be at least 8 characters long."})

        return data

    def change_password(self, user):
        new_password = self.validated_data['new_password']
        user.set_password(new_password)
        user.save()
        return user


class DoctorProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    # Editable user fields
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)

    # Editable profile fields
    current_position = serializers.CharField(required=False)
    workplace = serializers.CharField(required=False)
    nationality = serializers.CharField(required=False)
    residency = serializers.CharField(required=False)
    country_code = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    specialty = serializers.CharField(required=False)

    class Meta:
        model = DoctorProfile
        fields = [
            'username', 'email',
            'first_name', 'last_name',
            'current_position', 'workplace', 'nationality',
            'residency', 'country_code', 'phone_number', 'specialty',
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user

        for attr in ['first_name', 'last_name']:
            if attr in user_data:
                setattr(user, attr, user_data[attr])
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance
