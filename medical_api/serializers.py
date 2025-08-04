from django.contrib.auth import get_user_model
from rest_framework import serializers, mixins, viewsets
from django.contrib.auth.models import User
import re

from rest_framework.permissions import IsAuthenticated

from dashboard.models import DoctorProfile, ProductCategory, ProductSubCategory, ProductLastCategory, Event, Product, \
    SupplierProfile, Residency, Speciality, Nationality, CountryCode,SubscriptionPlan, UserSubscription
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

    # DoctorProfile fields (use integer IDs for ForeignKey relations)
    current_position = serializers.CharField()
    workplace = serializers.CharField()
    nationality = serializers.IntegerField()
    residency = serializers.IntegerField()
    country_code = serializers.IntegerField()
    phone_number = serializers.CharField()
    specialty = serializers.IntegerField()

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
    
    def to_representation(self, instance):
        data = {
            "id": instance.id,
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
        }

        try:
            profile = instance.doctor_profile
            data["doctor_profile"] = {
                "current_position": profile.current_position,
                "workplace": profile.workplace,
                "phone_number": profile.phone_number,
                "specialty": str(profile.speciality),
                "residency": str(profile.residency),
                "nationality": str(profile.nationality),
                "country_code": str(profile.country_code),
            }
        except DoctorProfile.DoesNotExist:
            data["doctor_profile"] = None

        return data


    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")

        password = data['password']
        # Password strength checks
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
            'phone_number': validated_data.pop('phone_number'),
        }

        # Pop and fetch related models using IDs
        try:
            profile_fields['nationality'] = Nationality.objects.get(id=validated_data.pop('nationality'))
            profile_fields['residency'] = Residency.objects.get(id=validated_data.pop('residency'))
            profile_fields['country_code'] = CountryCode.objects.get(id=validated_data.pop('country_code'))
            profile_fields['speciality'] = Speciality.objects.get(id=validated_data.pop('specialty'))
        except (Nationality.DoesNotExist, Residency.DoesNotExist, CountryCode.DoesNotExist, Speciality.DoesNotExist) as e:
            raise serializers.ValidationError({"detail": str(e)})

        validated_data.pop('confirm_password')

        # Create user
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


# class DoctorProfileSerializer(serializers.ModelSerializer):
#     username = serializers.CharField(source='user.username', read_only=True)
#     email = serializers.EmailField(source='user.email', read_only=True)
#
#     # Editable user fields
#     first_name = serializers.CharField(source='user.first_name', required=False)
#     last_name = serializers.CharField(source='user.last_name', required=False)
#
#     # Editable profile fields
#     current_position = serializers.CharField(required=False)
#     workplace = serializers.CharField(required=False)
#     nationality = serializers.CharField(required=False)
#     residency = serializers.CharField(required=False)
#     country_code = serializers.CharField(required=False)
#     phone_number = serializers.CharField(required=False)
#     specialty = serializers.CharField(required=False)
#
#     class Meta:
#         model = DoctorProfile
#         fields = [
#             'username', 'email',
#             'first_name', 'last_name',
#             'current_position', 'workplace', 'nationality',
#             'residency', 'country_code', 'phone_number', 'specialty',
#         ]
#
#     def update(self, instance, validated_data):
#         user_data = validated_data.pop('user', {})
#         user = instance.user
#
#         for attr in ['first_name', 'last_name']:
#             if attr in user_data:
#                 setattr(user, attr, user_data[attr])
#         user.save()
#
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#
#         return instance

class DoctorProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    nationality_name = serializers.CharField(source='nationality.name', read_only=True)
    residency_name = serializers.CharField(source='residency.name', read_only=True)
    country_code_name = serializers.CharField(source='country_code.code', read_only=True)
    country__name = serializers.CharField(source='country_code.country', read_only=True)
    specialty_name = serializers.CharField(source='specialty.name', read_only=True)


    # Editable user fields
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)

    # ForeignKey fields (accept ID on input, show string on output)
    nationality = serializers.PrimaryKeyRelatedField(
        queryset=Nationality.objects.all(), required=False
    )
    residency = serializers.PrimaryKeyRelatedField(
        queryset=Residency.objects.all(), required=False
    )
    country_code = serializers.PrimaryKeyRelatedField(
        queryset=CountryCode.objects.all(), required=False
    )
    specialty = serializers.PrimaryKeyRelatedField(
        queryset=Speciality.objects.all(), required=False
    )

    class Meta:
        model = DoctorProfile
        fields = [
            'username', 'email',
            'first_name', 'last_name',
            'current_position', 'workplace',
            'nationality', 'residency', 'country_code', 'phone_number', 'specialty',
            'nationality_name', 'residency_name', 'country_code_name', 'country__name','specialty_name'
        ]

    def update(self, instance, validated_data):
        # Update user fields
        user_data = validated_data.pop('user', {})
        user = instance.user
        for attr in ['first_name', 'last_name']:
            if attr in user_data:
                setattr(user, attr, user_data[attr])
        user.save()

        # Update profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name']

class ProductSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSubCategory
        fields = ['id', 'name', 'category']

class ProductLastCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductLastCategory
        fields = ['id', 'name', 'sub_category']


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all(), source='event', write_only=True, required=False)
    category_name = serializers.CharField(source="category.name", read_only=True)
    sub_category_name = serializers.CharField(source="sub_category.name", read_only=True)
    last_category_name = serializers.CharField(source="last_category.name", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True)

    class Meta:
        model = Product
        fields = '__all__'


# category": 1,
# "sub_category": 2,
# "last_category": 2,
# "brand": 2,
# "created_by

class EventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['conference_link', 'speaker_name', 'conference_at', 'duration', 'venue']

class ProductCreateSerializer(serializers.ModelSerializer):
    event_data = EventCreateSerializer(write_only=True, required=False)
    brochure = serializers.FileField(required=False)
    created_by = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
        required=False,
        write_only=True
    )

    class Meta:
        model = Product
        exclude = ['created_at']

    def create(self, validated_data):
        request = self.context.get("request")
        event_data = validated_data.pop('event_data', None)

        # Handle event creation
        if event_data:
            event = Event.objects.create(**event_data)
            validated_data['event'] = event

        # Assign created_by
        if request.user.is_staff or request.user.is_superuser:
            created_by_id = self.initial_data.get("created_by")
            if created_by_id:
                try:
                    validated_data["created_by"] = get_user_model().objects.get(id=created_by_id)
                except get_user_model().DoesNotExist:
                    raise serializers.ValidationError({"created_by": "Invalid user ID."})
            else:
                validated_data["created_by"] = request.user
        else:
            validated_data["created_by"] = request.user

        return Product.objects.create(**validated_data)


class UserEmailSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class SupplierListSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.id', read_only=True)
    email =serializers.CharField(source='user.email', read_only=True)
    username =serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = SupplierProfile
        fields = ['user_id', 'email', 'username']


class SpecialitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Speciality
        fields = ['id', 'name']


class ResidencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Residency
        fields = ['id', 'country']


class NationalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Nationality
        fields = ['id', 'country']


class CountryCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CountryCode
        fields = ['id', 'country', 'code']






class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
    
    def validate(self, data):
        if data['client_type'] == 'buyer' and not data.get('buyer_type'):
            raise serializers.ValidationError("Buyer type is required for buyer plans")
        if data['client_type'] == 'supplier' and data.get('buyer_type'):
            data['buyer_type'] = None
        return data




class UserSubscriptionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(write_only=True)  # Add this field
    
    class Meta:
        model = UserSubscription
        fields = ['user_email', 'plan', 'platform', 'subscription_date', 'is_active', 'platform_plan_id']
        read_only_fields = ('subscription_date', 'platform_plan_id', 'is_active')
    
    def validate(self, data):
        user_email = data.get('user_email')
        plan = data.get('plan')
        platform = data.get('platform')
        
        # Validate user exists
        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"user_email": "User with this email does not exist"})
        
        # Validate plan exists and has platform ID
        if not plan:
            raise serializers.ValidationError({"plan": "This field is required."})
        
        if platform == 'ios' and not plan.ios_plan_id:
            raise serializers.ValidationError({"platform": "This plan doesn't have an iOS plan ID"})
        if platform == 'android' and not plan.android_plan_id:
            raise serializers.ValidationError({"platform": "This plan doesn't have an Android plan ID"})
        
        data['user'] = user  # Add user object to validated data
        return data
