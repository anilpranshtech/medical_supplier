from django.contrib.auth import get_user_model
from rest_framework import serializers, mixins, viewsets
from django.contrib.auth.models import User
from rest_framework.reverse import reverse

from supplier.models import *
from superuser.models import *
from dashboard.models import *
import re

from rest_framework.permissions import IsAuthenticated

from dashboard.models import DoctorProfile, ProductCategory, ProductSubCategory, ProductLastCategory, Event, Product, \
    SupplierProfile, Residency, Speciality, Nationality, CountryCode,SubscriptionPlan, UserSubscription , CartProduct, Product,WishlistProduct,CustomerBillingAddress, SupplierProfile ,WholesaleBuyerProfile 
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


class ProductSerializer(serializers.ModelSerializer):
    main_image = serializers.SerializerMethodField()
    delivery_date = serializers.SerializerMethodField()
    rating = serializers.FloatField()
    total_reviews = serializers.IntegerField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'price', 'offer_percentage', 'main_image',
            'delivery_date', 'rating', 'total_reviews'
        ]

    def get_main_image(self, obj):
        if hasattr(obj, 'main_image') and obj.main_image:
            return self.context['request'].build_absolute_uri(obj.main_image)
        return None

    def get_delivery_date(self, obj):
        return obj.delivery_date if hasattr(obj, 'delivery_date') else 'N/A'


class RatingReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = RatingReview
        fields = ['id', 'rating', 'review', 'photo', 'created_at']
        read_only_fields = ['id', 'created_at']


class BannerSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()  # Explicitly define id as IntegerField
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = Banner
        fields = ['id', 'title', 'image', 'link', 'is_active', 'order']


class ProductSerializer(serializers.ModelSerializer):
    main_image = serializers.ImageField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'main_image']

    def get_main_image(self, obj):
        # Thanks to `to_attr='main_image'`, this avoids extra queries
        if hasattr(obj, 'main_image') and obj.main_image:
            return obj.main_image[0].image.url  # first main image
        return None


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    product_main_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'price', 'quantity', 'product_main_image']

    def get_product_main_image(self, obj):
        product = obj.product
        if hasattr(product, 'main_image') and product.main_image:
            return product.main_image[0].image.url
        return None


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'payment_method', 'created_at', 'amount', 'name']


class StripePaymentSerializer(serializers.ModelSerializer):
    card_last4 = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = StripePayment
        fields = ['id', 'stripe_charge_id', 'amount', 'created_at', 'name', 'stripe_customer_id', 'stripe_signature', 'card_last4']


class RazorpayPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RazorpayPayment
        fields = ['id', 'razorpay_payment_id', 'amount', 'created_at', 'name', 'razorpay_order_id', 'razorpay_signature']


class CODPaymentSerializer(serializers.ModelSerializer):
    delivery_partner = serializers.StringRelatedField()  # Returns the string representation of DeliveryPartner

    class Meta:
        model = CODPayment
        fields = ['id', 'amount', 'created_at', 'name', 'cod_tracking_id', 'delivery_partner']


class BankTransferPaymentSerializer(serializers.ModelSerializer):
    proof_image = serializers.ImageField(use_url=True, allow_null=True)

    class Meta:
        model = BankTransferPayment
        fields = ['id', 'name', 'amount', 'created_at', 'verified_by_admin', 'admin_notes', 'proof_image']


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product

        fields = ['id', 'name', 'price']


class CartProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', read_only=True, max_digits=10, decimal_places=2)
    product_image = serializers.SerializerMethodField()
    product = ProductSerializer(read_only=True)

    class Meta:
        model = CartProduct
        fields = ['id', 'product', 'product_name', 'product_price', 'quantity', 'product_image', 'created_at']

    def get_product_image(self, obj):
        try:
            request = self.context.get('request')
            if obj.product.images.exists():
                image_url = obj.product.images.first().image.url
                if request is not None:
                    return request.build_absolute_uri(image_url)
                return image_url  # fallback to relative URL
            return None
        except AttributeError:
            return None


class WishlistProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name')
    price = serializers.SerializerMethodField()
    sku = serializers.CharField(source='product.supplier_sku')
    image = serializers.SerializerMethodField()

    class Meta:
        model = WishlistProduct
        fields = ['id', 'product', 'product_name', 'price', 'sku', 'image']

    def get_price(self, obj):
        return f"${obj.product.price}"

    def get_image(self, obj):
        main_image = obj.product.productimage_set.first()
        return main_image.image.url if main_image else None


class CustomerBillingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerBillingAddress
        fields = ['id','address_title','customer_address1','customer_address2','phone','customer_city','customer_state','customer_country','customer_postal_code',]
        read_only_fields = ['user', 'is_deleted']


class OrderSerializer(serializers.ModelSerializer):
    payment = PaymentSerializer()
    main_image = serializers.SerializerMethodField()
    user_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'order_id', 'payment', 'shipping_fees', 'created_at', 'status', 'main_image', 'user_reviews']

    def get_main_image(self, obj):
        # Access prefetched main_image
        request = self.context.get('request')  # Get request from serializer context
        for item in obj.items.all():
            if hasattr(item.product, 'main_image') and item.product.main_image:
                image_url = item.product.main_image[0].image.url
                # Build full URL using request.build_absolute_uri
                return request.build_absolute_uri(image_url) if request else image_url
        return None

    def get_user_reviews(self, obj):
        # Access prefetched user_reviews
        reviews = []
        for item in obj.items.all():
            if hasattr(item.product, 'user_reviews'):
                reviews.extend(RatingReviewSerializer(item.product.user_reviews, many=True, context=self.context).data)
        return reviews


class RFQRequestSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    requested_by = serializers.StringRelatedField(read_only=True)
    quoted_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = RFQRequest
        fields = [
            'id', 'product', 'product_id', 'quantity', 'message', 'company_name',
            'expected_delivery_date', 'status', 'created_at', 'updated_at',
            'quoted_by', 'requested_by', 'email_sent'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status', 'email_sent', 'quoted_by', 'requested_by']


class RetailProfileSerializer(serializers.ModelSerializer):
    profile_picture = serializers.ImageField(use_url=True, allow_null=True)

    class Meta:
        model = RetailProfile
        fields = ['profile_picture', 'phone', 'current_position', 'workplace', 'nationality', 'residency', 'country_code', 'speciality']


class WholesaleBuyerProfileSerializer(serializers.ModelSerializer):
    profile_picture = serializers.ImageField(use_url=True, allow_null=True)

    class Meta:
        model = WholesaleBuyerProfile
        fields = ['profile_picture', 'company_name', 'gst_number', 'department', 'purchase_capacity']


class SupplierProfileSerializer(serializers.ModelSerializer):
    profile_picture = serializers.ImageField(use_url=True, allow_null=True)

    class Meta:
        model = SupplierProfile
        fields = ['profile_picture', 'company_name', 'license_number']

    
class RoleRequestSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = RoleRequest
        fields = ['id', 'user', 'requested_role', 'status', 'created_at', 'updated_at', 'profile']
        read_only_fields = ['id', 'user', 'status', 'created_at', 'updated_at']

    def get_profile(self, obj):
        serializer_context = {'request': self.context.get('request')}
        if obj.requested_role == 'retailer':
            profile = RetailProfile.objects.filter(user=obj.user).first()
            return RetailProfileSerializer(profile, context=serializer_context).data if profile else None
        elif obj.requested_role == 'wholesaler':
            profile = WholesaleBuyerProfile.objects.filter(user=obj.user).first()
            return WholesaleBuyerProfileSerializer(profile, context=serializer_context).data if profile else None
        elif obj.requested_role == 'supplier':
            profile = SupplierProfile.objects.filter(user=obj.user).first()
            return SupplierProfileSerializer(profile, context=serializer_context).data if profile else None
        return None

    def validate_requested_role(self, value):
        valid_roles = [choice[0] for choice in RoleRequest.ROLE_CHOICES]
        if value not in valid_roles:
            raise serializers.ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return value
        fields = ['id','address_title','customer_address1','customer_address2','phone','customer_city','customer_state','customer_country','customer_postal_code',]
        read_only_fields = ['user', 'is_deleted']


class ShippingInfoSerializer(serializers.Serializer):
  
    addresses = CustomerBillingAddressSerializer(many=True)
    default_address = CustomerBillingAddressSerializer()
    cart_items = CartProductSerializer(many=True)
    order_summary = serializers.DictField()


class ProductListSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'price', 'discounted_price',
            'category', 'sub_category', 'last_category',
            'is_active', 'created_at', 'image', 'link'
        ]

    def get_discounted_price(self, obj):
        return obj.discounted_price()

    def get_image(self, obj):
        request = self.context.get('request')
        image_url = obj.get_main_image()
        if image_url and request:
            return request.build_absolute_uri(image_url)
        return image_url or '/static/default_product.png'

    def get_link(self, obj):
        request = self.context.get('request')
        return reverse('medical_api:product-detail', kwargs={'id': obj.id}, request=request)


class WholesaleRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone = serializers.CharField()
    company_name = serializers.CharField()
    gst_number = serializers.CharField()
    department = serializers.CharField()
    purchase_capacity = serializers.IntegerField()

    class Meta:
        model = User
        fields = (
            'first_name', 'last_name', 'email', 'password', 'confirm_password',
            'phone', 'company_name', 'gst_number', 'department', 'purchase_capacity'
        )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        password = data['password']
        if len(password) < 8:
            raise serializers.ValidationError({"password": "Password must be at least 8 characters."})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')

        profile_fields = {
            'phone': validated_data.pop('phone'),
            'company_name': validated_data.pop('company_name'),
            'gst_number': validated_data.pop('gst_number'),
            'department': validated_data.pop('department'),
            'purchase_capacity': validated_data.pop('purchase_capacity'),
        }

        username = validated_data['email']

        try:
            user = User.objects.create_user(username=username, **validated_data)
            WholesaleBuyerProfile.objects.create(user=user, **profile_fields)
        except IntegrityError:
            raise serializers.ValidationError("A user with this email already exists.")

        return user

    def to_representation(self, instance):
        data = {
            "id": instance.id,
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
        }
        try:
            profile = instance.wholesalebuyerprofile
            data["wholesale_profile"] = {
                "phone": profile.phone,
                "company_name": profile.company_name,
                "gst_number": profile.gst_number,
                "department": profile.department,
                "purchase_capacity": profile.purchase_capacity
            }
        except WholesaleBuyerProfile.DoesNotExist:
            data["wholesale_profile"] = None
        return data


class SupplierRegistrationSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    company_name = serializers.CharField()
    license_number = serializers.CharField()

    def validate_email(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': "Passwords do not match."})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )

        supplier = SupplierProfile.objects.create(
            user=user,
            phone=validated_data['phone'],
            company_name=validated_data['company_name'],
            license_number=validated_data['license_number']
        )
        return supplier


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


class WholesaleBuyerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WholesaleBuyerProfile
        fields = '__all__'
        read_only_fields = ['user']


class SupplierProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierProfile
        fields = [
            'profile_picture',
            'phone',
            'company_name',
            'license_number',
            # 'is_verified'
        ]
        read_only_fields = ['is_verified']


class SuperUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "username", "email", "first_name", "last_name",
            "is_superuser", "is_staff", "date_joined", "last_login"
        ]


################################### NO LOGIN REQUIRED API's #################################

class LoginEventSerializer(serializers.ModelSerializer):
    duration = serializers.CharField(source='duration', read_only=True, allow_null=True)
    class Meta:
        model = Event
        fields = ['conference_at', 'speaker_name', 'venue', 'duration', 'conference_link']


class LoginProductSerializer(serializers.ModelSerializer):
    main_image = serializers.URLField(read_only=True)
    delivery_date = serializers.CharField(read_only=True)
    rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    discounted_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    event_details = serializers.DictField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    sub_category_name = serializers.CharField(read_only=True)
    last_category_name = serializers.CharField(read_only=True)
    brand_name = serializers.CharField(read_only=True)
    supplier_sku = serializers.CharField(read_only=True)  # Added to match Product model

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'main_image', 'price',  # Removed 'original_price'
            'offer_percentage', 'offer_active', 'delivery_date', 'rating', 'total_reviews',
            'supplier_sku', 'category', 'sub_category', 'last_category', 'category_name',
            'sub_category_name', 'last_category_name', 'brand_name', 'discounted_price',
            'event_details', 'show_rfq', 'show_add_to_cart', 'Both'
        ]


class LoginBannerSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True)
    class Meta:
        model = Banner
        fields = ['id', 'title', 'image', 'link']


class CategorySerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True, allow_null=True)
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'image']


class SupplierSerializer(serializers.ModelSerializer):
    company_logo = serializers.ImageField(use_url=True, allow_null=True)
    class Meta:
        model = SupplierProfile
        fields = ['id', 'company_name', 'company_logo']