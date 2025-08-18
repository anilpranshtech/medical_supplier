from decimal import Decimal
from io import BytesIO
from django.db.models import Q, F, DecimalField, ExpressionWrapper, Case, When
from django.http import HttpResponse
from django.utils.html import strip_tags
from xhtml2pdf import pisa
from django.template.loader import render_to_string
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from django.contrib.auth.models import User
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import viewsets, status, response, permissions, mixins, generics, views
from django.utils.timezone import now
from medical_api.serializers import *
from django.contrib.auth import get_user_model, login, authenticate, logout
from rest_framework.response import Response
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Avg, Prefetch
import random
from dashboard.models import PasswordUpdateTracker, ProductCategory, ProductSubCategory, ProductLastCategory, Product, \
    SupplierProfile,SubscriptionPlan, UserSubscription ,CartProduct,WishlistProduct,CustomerBillingAddress,RetailProfile, WholesaleBuyerProfile, SupplierProfile,ProductCategory, ProductLastCategory,SupplierProfile
from medical_api.serializers import UserLoginSerializer, DoctorRegistrationSerializer, ChangePasswordSerializer, \
    DoctorProfileSerializer, ProductCategorySerializer, ProductSubCategorySerializer, ProductLastCategorySerializer, \
    ProductSerializer, ProductCreateSerializer, UserEmailSerializer, SupplierListSerializer, ResidencySerializer, \
    SpecialitySerializer, NationalitySerializer, CountryCodeSerializer,SubscriptionPlanSerializer, UserSubscriptionSerializer,CartProductSerializer,WishlistProductSerializer,CustomerBillingAddressSerializer,ShippingInfoSerializer, ProductSerializer,SupplierProfileSerializer,WholesaleBuyerProfileSerializer,WholesaleRegistrationSerializer
from django.contrib.auth import get_user_model, login, authenticate, logout
from rest_framework.response import Response
from decimal import Decimal

UserModel = get_user_model()
from dashboard.models import *
from supplier.models import *
from superuser.models import *
from django.conf import settings
import re
from rest_framework.pagination import PageNumberPagination
import logging
logger = logging.getLogger(__name__)

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def format_response(data=None, message="Success", code=status.HTTP_200_OK, paginated=False, pagination_data=None):
    response_data = {
        "code": code,
        "message": message,
        "items": {
            "data": data
        }
    }
    
    if paginated and pagination_data:
        response_data["items"]["current_page"] = pagination_data.get('current_page', 1)
        response_data["items"]["total_pages"] = pagination_data.get('total_pages')
        response_data["items"]["total_items"] = pagination_data.get('total_items')
    
    return Response(response_data, status=code)



class CustomPagination(PageNumberPagination):
    page_size = 10 
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "code": status.HTTP_200_OK,
            "message": "Success",
            "items": {
                "current_page": self.page.number,
                "total_pages": self.page.paginator.num_pages,
                "total_items": self.page.paginator.count,
                "page_size": self.page_size,
                "data": data
            }
        })


class UserLoginAdminView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, format=None):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.data.get("email")
            password = serializer.data.get("password")
            user = authenticate(email=email, password=password)

            user_data = UserModel.objects.filter(email=email).last()
            if user is not None:
                login(request, user)
                token = get_tokens_for_user(user)
                token_data = {
                    "status": True,
                    "username": str(user),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "refresh": token['refresh'],
                    "access": token['access']
                }

                if user.is_superuser:
                    token_data["account_role"] = 'Administrator'
                elif user.is_staff and user.is_active:
                    token_data["account_role"] = 'Staff'
                elif not user.is_staff and user.is_active:
                    token_data["account_role"] = 'User'

                if user.is_staff or user.is_superuser:
                    try:
                        try:
                            user_last_modified = PasswordUpdateTracker.objects.get(user=user)
                        except:
                            user_last_modified = PasswordUpdateTracker.objects.create(
                                user=user,
                                last_password_update=user.date_joined
                            )
                        if user_last_modified:
                            token_data['Update_password_required'] = user_last_modified.is_password_expired()
                        else:
                            token_data['Update_password_required'] = True

                    except PasswordUpdateTracker.DoesNotExist:
                        token_data['Update_password_required'] = None

                return format_response(data=token_data)
            else:
                return format_response(
                    data=None,
                    message="Email or Password is not valid",
                    code=status.HTTP_404_NOT_FOUND
                )
        else:
            return format_response(
                data=None,
                message="Email or Password is not valid",
                code=status.HTTP_400_BAD_REQUEST
            )


class DoctorRegisterAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request, format=None):
        serializer = DoctorRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return format_response(
                data={"email": serializer.data.get('email')},
                message="Registration successful",
                code=status.HTTP_201_CREATED
            )
        return format_response(
            data=serializer.errors,
            message="Registration failed",
            code=status.HTTP_400_BAD_REQUEST
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data, context={'user': user})

        if serializer.is_valid():
            serializer.change_password(user)

            if user.is_superuser and user.is_staff:
                PasswordUpdateTracker.objects.update_or_create(
                    user=user,
                    defaults={'last_password_update': now()}
                )

            return format_response(
                data={"email": user.email},
                message="Password updated successfully"
            )

        return format_response(
            data=serializer.errors,
            message="Password update failed",
            code=status.HTTP_400_BAD_REQUEST
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return format_response(message="Successfully logged out.")
        except KeyError:
            return format_response(
                data=None,
                message="Refresh token is required.",
                code=status.HTTP_400_BAD_REQUEST
            )
        except TokenError as e:
            return format_response(
                data=None,
                message=str(e),
                code=status.HTTP_400_BAD_REQUEST
            )


class ForgotPasswordAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        email = request.data.get('email')
        User = get_user_model()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return format_response(
                data=None,
                message="No account found with this email.",
                code=status.HTTP_400_BAD_REQUEST
            )

        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        return format_response(
            data={
                'token': token,
                'uid': uid
            },
            message="Password reset credentials."
        )


class ResetPasswordAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request, uidb64, token):
        password = request.data.get('password')
        confirm_password = request.data.get('confirm_password')

        if not password or not confirm_password:
            return format_response(
                data=None,
                message="Password and confirm password are required.",
                code=status.HTTP_400_BAD_REQUEST
            )

        if password != confirm_password:
            return format_response(
                data=None,
                message="Passwords do not match.",
                code=status.HTTP_400_BAD_REQUEST
            )

        if len(password) < 8:
            return format_response(
                data=None,
                message="Password must be at least 8 characters long.",
                code=status.HTTP_400_BAD_REQUEST
            )
        if not re.search(r'[A-Z]', password):
            return format_response(
                data=None,
                message="Password must contain at least one uppercase letter.",
                code=status.HTTP_400_BAD_REQUEST
            )
        if not re.search(r'[a-z]', password):
            return format_response(
                data=None,
                message="Password must contain at least one lowercase letter.",
                code=status.HTTP_400_BAD_REQUEST
            )
        if not re.search(r'[0-9]', password):
            return format_response(
                data=None,
                message="Password must contain at least one number.",
                code=status.HTTP_400_BAD_REQUEST
            )
        if not re.search(r'[\W_]', password):
            return format_response(
                data=None,
                message="Password must contain at least one special character.",
                code=status.HTTP_400_BAD_REQUEST
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = get_user_model().objects.get(pk=uid)
        except Exception:
            return format_response(
                data=None,
                message="Invalid or expired link.",
                code=status.HTTP_400_BAD_REQUEST
            )

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return format_response(
                data=None,
                message="Invalid or expired token.",
                code=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(password)
        user.save()
        return format_response(message="Password has been reset successfully.")


class DoctorProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.doctor_profile
        serializer = DoctorProfileSerializer(profile)
        return format_response(data=serializer.data)

    def put(self, request):
        profile = request.user.doctor_profile
        serializer = DoctorProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return format_response(data=serializer.data)
        return format_response(
            data=serializer.errors,
            message="Profile update failed",
            code=status.HTTP_400_BAD_REQUEST
        )


class CategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination  

    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or None.
        """
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        """
        Return a single page of results, or `None` if pagination is disabled.
        """
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        """
        Return a paginated style `Response` object for the given output data.
        """
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

    def get(self, request):
        categories = ProductCategory.objects.all()
        
        no_page = request.query_params.get('no_page', '').lower() in ('true', '1')
        
        if no_page:
            serializer = ProductCategorySerializer(categories, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Success",
                "items": {
                    "data": serializer.data
                }
            })
        
        
        page = self.paginate_queryset(categories)
        if page is not None:
            serializer = ProductCategorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
       
        serializer = ProductCategorySerializer(categories, many=True)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "Success",
            "items": {
                "data": serializer.data
            }
        })

    def post(self, request):
        serializer = ProductCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "code": status.HTTP_201_CREATED,
                "message": "Category created",
                "items": {
                    "data": serializer.data
                }
            }, status=status.HTTP_201_CREATED)
        return Response({
            "code": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "items": {
                "errors": serializer.errors
            }
        }, status=status.HTTP_400_BAD_REQUEST)




class SubCategoryListByCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination  # Add pagination class

    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or None.
        """
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        """
        Return a single page of results, or `None` if pagination is disabled.
        """
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        """
        Return a paginated style `Response` object for the given output data.
        """
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

    def get(self, request):
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "category_id is required",
                "items": {
                    "errors": ["category_id query parameter is required"]
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        subcategories = ProductSubCategory.objects.filter(category_id=category_id)
        
        # Check if pagination is disabled via query param
        no_page = request.query_params.get('no_page', '').lower() in ('true', '1')
        
        if no_page:
            serializer = ProductSubCategorySerializer(subcategories, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Success",
                "items": {
                    "data": serializer.data
                }
            })
        
        # Paginate the queryset
        page = self.paginate_queryset(subcategories)
        if page is not None:
            serializer = ProductSubCategorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Fallback for non-paginated response
        serializer = ProductSubCategorySerializer(subcategories, many=True)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "Success",
            "items": {
                "data": serializer.data
            }
        })

    def post(self, request):
        serializer = ProductSubCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "code": status.HTTP_201_CREATED,
                "message": "Subcategory created",
                "items": {
                    "data": serializer.data
                }
            }, status=status.HTTP_201_CREATED)
        return Response({
            "code": status.HTTP_400_BAD_REQUEST,
            "message": "Subcategory creation failed",
            "items": {
                "errors": serializer.errors
            }
        }, status=status.HTTP_400_BAD_REQUEST)





class LastCategoryListBySubCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub_category_id = request.query_params.get('sub_category_id')
        if not sub_category_id:
            return format_response(
                data=None,
                message="sub_category_id is required",
                code=status.HTTP_400_BAD_REQUEST
            )

        last_categories = ProductLastCategory.objects.filter(sub_category_id=sub_category_id)
        serializer = ProductLastCategorySerializer(last_categories, many=True)
        return format_response(data=serializer.data)

    def post(self, request):
        serializer = ProductLastCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return format_response(
                data=serializer.data,
                message="Last category created",
                code=status.HTTP_201_CREATED
            )
        return format_response(
            data=serializer.errors,
            message="Last category creation failed",
            code=status.HTTP_400_BAD_REQUEST
        )


class ProductListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = CustomPagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        no_page = request.query_params.get('no_page', '').lower() in ('true', '1')
        
        if no_page:
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Success",
                "items": {
                    "data": serializer.data
                }
            })
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "Success",
            "items": {
                "data": serializer.data
            }
        })



class ProductDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return format_response(data=serializer.data)


class ProductCreateAPIView(CreateAPIView):
    serializer_class = ProductCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return format_response(
                data=serializer.data,
                message="Product created successfully",
                code=status.HTTP_201_CREATED
            )
        return format_response(
            data=serializer.errors,
            message="Product creation failed",
            code=status.HTTP_400_BAD_REQUEST
        )


class UserEmailViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserEmailSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return format_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return format_response(data=serializer.data)


class SupplierList(viewsets.ReadOnlyModelViewSet):
    queryset = SupplierProfile.objects.all()
    serializer_class = SupplierListSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return format_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return format_response(data=serializer.data)


class SpecialityListView(ListAPIView):
    serializer_class = SpecialitySerializer

    def get_queryset(self):
        return Speciality.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return format_response(data=[], message="No specialties found")
        serializer = self.get_serializer(queryset, many=True)
        return format_response(data=serializer.data, message="Specialties fetched successfully")


class ResidencyListView(ListAPIView):
    serializer_class = ResidencySerializer

    def get_queryset(self):
        return Residency.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return format_response(data=[], message="No residencies found")
        serializer = self.get_serializer(queryset, many=True)
        return format_response(data=serializer.data, message="Residencies fetched successfully")


class NationalityListView(ListAPIView):
    serializer_class = NationalitySerializer

    def get_queryset(self):
        return Nationality.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return format_response(data=[], message="No nationalities found")
        serializer = self.get_serializer(queryset, many=True)
        return format_response(data=serializer.data, message="Nationalities fetched successfully")


class CountryCodeListView(ListAPIView):
    serializer_class = CountryCodeSerializer

    def get_queryset(self):
        return CountryCode.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return format_response(data=[], message="No country codes found")
        serializer = self.get_serializer(queryset, many=True)
        return format_response(data=serializer.data, message="Country codes fetched successfully")





class SubscriptionPlanListCreateAPIView(generics.ListCreateAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        client_type = self.request.query_params.get('client_type')
        buyer_type = self.request.query_params.get('buyer_type')
        
        if client_type:
            queryset = queryset.filter(client_type=client_type)
            if client_type == 'buyer' and buyer_type:
                queryset = queryset.filter(buyer_type=buyer_type)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return format_response(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return format_response(
                data=serializer.data,
                message="Subscription plan created successfully",
                code=status.HTTP_201_CREATED
            )
        return format_response(
            data=serializer.errors,
            message="Validation error",
            code=status.HTTP_400_BAD_REQUEST
        )

class UserSubscriptionListAPIView(generics.ListAPIView):
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserSubscription.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return format_response(data=serializer.data)



class UserSubscriptionCreateAPIView(generics.CreateAPIView):
    queryset = UserSubscription.objects.all()
    serializer_class = UserSubscriptionSerializer
    permission_classes = [AllowAny]  # Changed from IsAuthenticated

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Get the validated data
            user = serializer.validated_data['user']
            plan = serializer.validated_data['plan']
            platform = serializer.validated_data['platform']
            
            # Set platform_plan_id
            platform_plan_id = plan.ios_plan_id if platform == 'ios' else plan.android_plan_id
            
            # Create subscription
            subscription = UserSubscription.objects.create(
                user=user,
                plan=plan,
                platform=platform,
                platform_plan_id=platform_plan_id,
                is_active=True
            )
            
            return Response({
                "code": status.HTTP_201_CREATED,
                "message": "Subscription created successfully",
                "items": {
                    "data": UserSubscriptionSerializer(subscription).data
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            "code": status.HTTP_400_BAD_REQUEST,
            "message": "Validation error",
            "items": {
                "errors": serializer.errors
            }
        }, status=status.HTTP_400_BAD_REQUEST)


class HomeAPIViewSet(viewsets.ViewSet):
    def list(self, request):
        today = date.today()

        def set_product_fields(product_queryset):
            for product in product_queryset:
                main_img = ProductImage.objects.filter(product=product, is_main=True).first()
                product.main_image = main_img.image.url if main_img else None
                if product.delivery_time:
                    delivery_date = today + timedelta(days=product.delivery_time)
                    product.delivery_date = delivery_date.strftime('%a, %d %b')
                else:
                    product.delivery_date = 'N/A'
                reviews = RatingReview.objects.filter(product=product)
                total_reviews = reviews.count()
                average_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0.0
                product.rating = round(average_rating, 1) if total_reviews > 0 else 0.0
                product.total_reviews = total_reviews
            return product_queryset

        special_offers = Product.objects.filter(
            offer_active=True,
            offer_percentage__gt=0,
            offer_start__lte=today,
            offer_end__gte=today,
            is_active=True
        ).order_by('-offer_percentage')[:3]
        special_offers = set_product_fields(special_offers)

        recent_products = Product.objects.filter(
            tag='recent',
            is_active=True
        ).order_by('-created_at')[:4]
        recent_products = set_product_fields(recent_products)

        popular_products = Product.objects.filter(
            tag='popular',
            is_active=True
        ).order_by('-created_at')[:4]
        popular_products = set_product_fields(popular_products)

        limited_products = Product.objects.filter(
            tag='limited',
            is_active=True
        ).order_by('-created_at')[:4]
        limited_products = set_product_fields(limited_products)

        all_ids = list(Product.objects.filter(is_active=True).values_list('id', flat=True))
        random_ids = random.sample(all_ids, min(len(all_ids), 6))
        featured_products = Product.objects.filter(id__in=random_ids)
        featured_products = set_product_fields(featured_products)

        user_wishlist_ids = []
        user_cart_ids = []
        if request.user.is_authenticated:
            user_wishlist_ids = list(
                WishlistProduct.objects.filter(user=request.user)
                .values_list('product_id', flat=True)
            )
            user_cart_ids = list(
                CartProduct.objects.filter(user=request.user).values_list('product_id', flat=True)
            )

        banners = Banner.objects.filter(is_active=True)

        serializer_context = {'request': request}
        data = {
            # 'user_wishlist_ids': user_wishlist_ids,
            # 'user_cart_ids': user_cart_ids,
            'banners': BannerSerializer(banners, many=True, context=serializer_context).data,
            'featured_products': ProductSerializer(featured_products, many=True, context=serializer_context).data,
            'special_offers': ProductSerializer(special_offers, many=True, context=serializer_context).data,
            'recent_products': ProductSerializer(recent_products, many=True, context=serializer_context).data,
            'popular_products': ProductSerializer(popular_products, many=True, context=serializer_context).data,
            'limited_products': ProductSerializer(limited_products, many=True, context=serializer_context).data,
        }

        return Response(data)

class BannerViewSet(viewsets.ModelViewSet):
    queryset = Banner.objects.filter(is_active=True)
    serializer_class = BannerSerializer


class OrderPlacedAPIViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        try:
            payment = Payment.objects.filter(user=user).order_by('-created_at').first()
            if not payment:
                logger.error(f"No payment found for user {user.id}")
                return Response({"error": "No recent payment found."}, status=400)
        except ObjectDoesNotExist:
            logger.error(f"No payment found for user {user.id}")
            return Response({"error": "No recent payment found."}, status=400)

        order_exists = Order.objects.filter(payment=payment, user=user).exists()
        if not order_exists:
            logger.error(
                f"No order found for payment {payment.id} (method: {payment.payment_method}, created: {payment.created_at}) and user {user.id}"
            )
            recent_order = Order.objects.filter(user=user).order_by('-created_at').first()
            if recent_order:
                logger.warning(
                    f"Fallback: Found recent order {recent_order.order_id} for user {user.id}, but not linked to payment {payment.id}"
                )
            all_orders = Order.objects.filter(user=user).values('id', 'order_id', 'payment_id', 'created_at')
            all_payments = Payment.objects.filter(user=user).values('id', 'payment_method', 'created_at')
            logger.debug(f"All orders for user {user.id}: {list(all_orders)}")
            logger.debug(f"All payments for user {user.id}: {list(all_payments)}")
            return Response({"error": "No recent order found."}, status=400)

        logger.info(f"Found order for payment {payment.id} and user {user.id}")

        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        try:
            order = Order.objects.filter(
                user=user,
                payment=payment
            ).select_related(
                'payment'
            ).prefetch_related(main_image_prefetch).first()

            if not order:
                logger.error(f"No order found for payment {payment.id} and user {user.id}")
                order = Order.objects.filter(user=user).order_by('-created_at').first()
                if order:
                    logger.warning(f"Fallback: Using recent order {order.order_id} for user {user.id}, not linked to payment {payment.id}")
                else:
                    return Response({"error": "No order found for this payment."}, status=400)
        except ObjectDoesNotExist:
            return Response({"error": "No order found for this payment."}, status=400)

        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        max_delivery_days = max((item.product.delivery_time or 5) for item in order.items.all())
        estimated_delivery = timezone.now().date() + timedelta(days=max_delivery_days)

        time_window = payment.created_at + timedelta(minutes=10)
        payment_method = payment.payment_method
        payment_details = None

        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, time_window)
            ).order_by('-created_at').first()
        elif payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, time_window)
            ).order_by('-created_at').first()
        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, time_window)
            ).order_by('-created_at').first()
        elif payment_method == "bank_transfer":
            payment_details = BankTransferPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        billing = CustomerBillingAddress.objects.filter(
            user=user,
            is_default=True,
            is_deleted=False
        ).first()

        serializer_context = {'request': request}
        data = {
            'payment': PaymentSerializer(payment, context=serializer_context).data,
            'order': OrderSerializer(order, context=serializer_context).data,
            'order_items': OrderItemSerializer(order.items.all(), many=True, context=serializer_context).data,
            'order_summary': {
                'subtotal': str(subtotal),
                'shipping': str(shipping),
                'vat': str(vat),
                'total': str(total)
            },
            'order_id': order.order_id,
            'order_date': payment.created_at.isoformat(),
            'estimated_delivery': estimated_delivery.isoformat(),
            'payment_method': payment_method,
            'payment_details': (
                StripePaymentSerializer(payment_details, context=serializer_context).data if payment_method == "stripe" else
                RazorpayPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "razorpay" else
                CODPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "cod" else
                BankTransferPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "bank_transfer" else
                None
            ),
            'billing': CustomerBillingAddressSerializer(billing, context=serializer_context).data if billing else None,
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        }

        logger.info(f"Loaded order {order.order_id} for user {user.id} with payment {payment.id}, items: {order.items.count()}")
        return Response(data)


class MyOrdersAPIViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user

        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )
        user_reviews_prefetch = Prefetch(
            'items__product__reviews',
            queryset=RatingReview.objects.filter(user=user),
            to_attr='user_reviews'
        )

        orders_qs = Order.objects.filter(user=user).select_related('payment').prefetch_related(
            main_image_prefetch,
            user_reviews_prefetch
        ).order_by('-created_at')

        # Pagination
        paginator = Paginator(orders_qs, 2)  # 2 orders per page
        page_number = request.query_params.get('page', 1)
        page_obj = paginator.get_page(page_number)

        serializer_context = {'request': request}
        orders_data = OrderSerializer(page_obj.object_list, many=True, context=serializer_context).data

        data = {
            'orders': orders_data,
            'page': {
                'current_page': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'total_pages': paginator.num_pages,
                'total_items': paginator.count
            }
        }

        return Response(data)

class SubmitReviewAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            logger.error(f"Product {product_id} not found for user {request.user.id}")
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check for duplicate review
        if RatingReview.objects.filter(user=request.user, product=product).exists():
            logger.warning(f"User {request.user.id} already reviewed product {product_id}")
            return Response({"error": "You have already reviewed this product."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate input
        rating = request.data.get('rating')
        if not rating:
            logger.error(f"Rating is required for user {request.user.id} on product {product_id}")
            return Response({"error": "Rating is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError("Rating must be between 1 and 5.")
        except ValueError:
            logger.error(f"Invalid rating value {rating} for user {request.user.id} on product {product_id}")
            return Response({"error": "Rating must be an integer between 1 and 5."}, status=status.HTTP_400_BAD_REQUEST)

        # Create review
        review_data = {
            'product': product.id,
            'user': request.user.id,
            'rating': rating,
            'review': request.data.get('review'),
            'photo': request.FILES.get('photo')
        }
        serializer = RatingReviewSerializer(data=review_data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Review submitted by user {request.user.id} for product {product_id}")
            return Response({"message": "Your review has been submitted!"}, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Review validation failed for user {request.user.id}: {serializer.errors}")
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class ReorderAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found for user {request.user.id}")
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        order_items = OrderItem.objects.filter(order=order)
        if not order_items.exists():
            logger.error(f"No items found for order {order_id} and user {request.user.id}")
            return Response({"error": "No items found in this order."}, status=status.HTTP_400_BAD_REQUEST)

        # Add items to cart
        cart_items = []
        for item in order_items:
            cart_item, created = CartProduct.objects.get_or_create(
                user=request.user,
                product=item.product,
                defaults={'quantity': item.quantity}
            )
            if not created:
                cart_item.quantity += item.quantity
                cart_item.save()
            cart_items.append(cart_item)
            logger.info(f"Added {item.quantity} x {item.product.name} to cart for user {request.user.id}")

        serializer_context = {'request': request}
        cart_data = CartProductSerializer(cart_items, many=True, context=serializer_context).data
        return Response({
            "message": f"Added items from order {order.order_id} to your cart.",
            "cart_items": cart_data
        }, status=status.HTTP_200_OK)


class OrderReceiptAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        user = request.user
        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        try:
            order = Order.objects.filter(id=order_id, user=user).select_related('payment').prefetch_related(main_image_prefetch).get()
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found for user {user.id}")
            return Response({"error": "Order not found or you don't have permission to view it."}, status=status.HTTP_404_NOT_FOUND)

        payment = order.payment
        payment_method = payment.payment_method if payment else order.items.first().payment_type.lower()

        payment_details = None
        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
            if payment_details and payment_details.stripe_customer_id:
                billing_with_card = CustomerBillingAddress.objects.filter(user=user, is_old=True, is_deleted=False).first()
                if billing_with_card and billing_with_card.old_card:
                    try:
                        card_info = json.loads(billing_with_card.old_card.replace("'", "\""))
                        payment_details.card_last4 = card_info.get('last4', 'N/A')
                    except (json.JSONDecodeError, AttributeError):
                        payment_details.card_last4 = 'N/A'
                else:
                    payment_details.card_last4 = 'N/A'
        elif payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment_method == "bank_transfer":
            payment_details = BankTransferPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        max_delivery_days = max((item.product.delivery_time or 5) for item in order.items.all())
        estimated_delivery = order.created_at.date() + timedelta(days=max_delivery_days)

        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        serializer_context = {'request': request}
        data = {
            'order': OrderSerializer(order, context=serializer_context).data,
            'order_summary': {
                'subtotal': str(subtotal),
                'shipping': str(shipping),
                'vat': str(vat),
                'total': str(total)
            },
            'order_total': str(total),
            'order_date': order.created_at.isoformat(),
            'billing': CustomerBillingAddressSerializer(billing, context=serializer_context).data if billing else None,
            'estimated_delivery': estimated_delivery.isoformat(),
            'payment_method': payment_method,
            'payment_details': (
                StripePaymentSerializer(payment_details, context=serializer_context).data if payment_method == "stripe" else
                RazorpayPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "razorpay" else
                CODPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "cod" else
                BankTransferPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "bank_transfer" else
                None
            ),
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        }

        logger.info(f"Order receipt loaded for order {order.order_id} and user {user.id}")
        return Response(data)

class DownloadReceiptAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        user = request.user
        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        try:
            order = Order.objects.filter(id=order_id, user=user).select_related('payment').prefetch_related(main_image_prefetch).get()
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found for user {user.id}")
            return Response({"error": "Order not found or you don't have permission to view it."}, status=status.HTTP_404_NOT_FOUND)

        payment = order.payment
        payment_method = payment.payment_method if payment else order.items.first().payment_type.lower()

        payment_details = None
        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
            if payment_details and payment_details.stripe_customer_id:
                billing_with_card = CustomerBillingAddress.objects.filter(user=user, is_old=True, is_deleted=False).first()
                if billing_with_card and billing_with_card.old_card:
                    try:
                        card_info = json.loads(billing_with_card.old_card.replace("'", "\""))
                        payment_details.card_last4 = card_info.get('last4', 'N/A')
                    except (json.JSONDecodeError, AttributeError):
                        payment_details.card_last4 = 'N/A'
                else:
                    payment_details.card_last4 = 'N/A'
        elif payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment_method == "bank_transfer":
            payment_details = BankTransferPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        items = []
        for order_item in order.items.all():
            product_image = order_item.product.main_image[0] if order_item.product.main_image else None
            items.append({
                'product': order_item.product,
                'quantity': order_item.quantity,
                'sku': order_item.product.supplier_sku,
                'total_price': order_item.price * order_item.quantity,
                'image_url': request.build_absolute_uri(product_image.image.url) if product_image else None,
            })

        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        max_delivery_days = max((item.product.delivery_time or 5) for item in order.items.all())
        estimated_delivery = order.created_at.date() + timedelta(days=max_delivery_days)

        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        context = {
            'order': order,
            'items': items,
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'total': total,
            },
            'order_total': total,
            'order_date': order.created_at,
            'billing': billing,
            'estimated_delivery': estimated_delivery,
            'payment_method': payment_method,
            'payment_details': payment_details,
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        }

        html_string = render_to_string('userdashboard/view/order_receipt_pdf.html', context)
        result = BytesIO()
        pdf = pisa.CreatePDF(src=html_string, dest=result)
        if pdf.err:
            logger.error(f"Failed to generate PDF for order {order.order_id}: {pdf.err}")
            return Response({"error": "Error generating PDF"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="order_receipt_{order.order_id}.pdf"'
        response.write(result.getvalue())
        logger.info(f"Generated PDF receipt for order {order.order_id} and user {user.id}")
        return response


class MyOrdersAPIViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )
        user_reviews_prefetch = Prefetch(
            'items__product__reviews',
            queryset=RatingReview.objects.filter(user=user),
            to_attr='user_reviews'
        )
        orders_qs = Order.objects.filter(user=user).select_related('payment').prefetch_related(
            main_image_prefetch,
            user_reviews_prefetch
        ).order_by('-created_at')
        paginator = Paginator(orders_qs, 2)
        page_number = request.query_params.get('page', 1)
        page_obj = paginator.get_page(page_number)
        serializer_context = {'request': request}
        orders_data = OrderSerializer(page_obj.object_list, many=True, context=serializer_context).data
        data = {
            'orders': orders_data,
            'page': {
                'current_page': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'total_pages': paginator.num_pages,
                'total_items': paginator.count
            }
        }
        return Response(data)

class SubmitReviewAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            logger.error(f"Product {product_id} not found for user {request.user.id}")
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        if RatingReview.objects.filter(user=request.user, product=product).exists():
            logger.warning(f"User {request.user.id} already reviewed product {product_id}")
            return Response({"error": "You have already reviewed this product."}, status=status.HTTP_400_BAD_REQUEST)
        rating = request.data.get('rating')
        if not rating:
            logger.error(f"Rating is required for user {request.user.id} on product {product_id}")
            return Response({"error": "Rating is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError("Rating must be between 1 and 5.")
        except ValueError:
            logger.error(f"Invalid rating value {rating} for user {request.user.id} on product {product_id}")
            return Response({"error": "Rating must be an integer between 1 and 5."}, status=status.HTTP_400_BAD_REQUEST)
        review_data = {
            'product': product.id,
            'user': request.user.id,
            'rating': rating,
            'review': request.data.get('review'),
            'photo': request.FILES.get('photo')
        }
        serializer = RatingReviewSerializer(data=review_data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Review submitted by user {request.user.id} for product {product_id}")
            return Response({"message": "Your review has been submitted!"}, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Review validation failed for user {request.user.id}: {serializer.errors}")
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class ReorderAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found for user {request.user.id}")
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        order_items = OrderItem.objects.filter(order=order)
        if not order_items.exists():
            logger.error(f"No items found for order {order_id} and user {request.user.id}")
            return Response({"error": "No items found in this order."}, status=status.HTTP_400_BAD_REQUEST)
        cart_items = []
        for item in order_items:
            cart_item, created = CartProduct.objects.get_or_create(
                user=request.user,
                product=item.product,
                defaults={'quantity': item.quantity}
            )
            if not created:
                cart_item.quantity += item.quantity
                cart_item.save()
            cart_items.append(cart_item)
            logger.info(f"Added {item.quantity} x {item.product.name} to cart for user {request.user.id}")
        serializer_context = {'request': request}
        cart_data = CartProductSerializer(cart_items, many=True, context=serializer_context).data
        return Response({
            "message": f"Added items from order {order.order_id} to your cart.",
            "cart_items": cart_data
        }, status=status.HTTP_200_OK)

class OrderReceiptAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        user = request.user
        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        try:
            order = Order.objects.filter(id=order_id, user=user).select_related('payment').prefetch_related(main_image_prefetch).get()
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found for user {user.id}")
            return Response({"error": "Order not found or you don't have permission to view it."}, status=status.HTTP_404_NOT_FOUND)

        payment = order.payment
        payment_method = payment.payment_method if payment else (order.items.first().payment_type.lower() if order.items.exists() else "unknown")

        payment_details = None
        if payment and payment_method == "stripe":
            payment_details = StripePayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
            if payment_details and payment_details.stripe_customer_id:
                billing_with_card = CustomerBillingAddress.objects.filter(user=user, is_old=True, is_deleted=False).first()
                if billing_with_card and billing_with_card.old_card:
                    try:
                        card_info = json.loads(billing_with_card.old_card.replace("'", "\""))
                        payment_details.card_last4 = card_info.get('last4', 'N/A')
                    except (json.JSONDecodeError, AttributeError):
                        payment_details.card_last4 = 'N/A'
                else:
                    payment_details.card_last4 = 'N/A'
        elif payment and payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment and payment_method == "cod":
            payment_details = CODPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment and payment_method == "bank_transfer":
            payment_details = BankTransferPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        max_delivery_days = max((item.product.delivery_time or 5) for item in order.items.all()) if order.items.exists() else 5
        estimated_delivery = order.created_at.date() + timedelta(days=max_delivery_days)

        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        serializer_context = {'request': request}
        data = {
            'order': OrderSerializer(order, context=serializer_context).data,
            'order_summary': {
                'subtotal': str(subtotal),
                'shipping': str(shipping),
                'vat': str(vat),
                'total': str(total)
            },
            'order_total': str(total),
            'order_date': order.created_at.isoformat(),
            'billing': CustomerBillingAddressSerializer(billing, context=serializer_context).data if billing else None,
            'estimated_delivery': estimated_delivery.isoformat(),
            'payment_method': payment_method,
            'payment_details': (
                StripePaymentSerializer(payment_details, context=serializer_context).data if payment_method == "stripe" else
                RazorpayPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "razorpay" else
                CODPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "cod" else
                BankTransferPaymentSerializer(payment_details, context=serializer_context).data if payment_method == "bank_transfer" else
                None
            ),
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        }

        logger.info(f"Order receipt loaded for order {order.order_id} and user {user.id}")
        return Response(data)

class DownloadReceiptAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        user = request.user
        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        try:
            order = Order.objects.filter(id=order_id, user=user).select_related('payment').prefetch_related(main_image_prefetch).get()
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found for user {user.id}")
            return Response({"error": "Order not found or you don't have permission to view it."}, status=status.HTTP_404_NOT_FOUND)

        payment = order.payment
        payment_method = payment.payment_method if payment else (order.items.first().payment_type.lower() if order.items.exists() else "unknown")

        payment_details = None
        if payment and payment_method == "stripe":
            payment_details = StripePayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
            if payment_details and payment_details.stripe_customer_id:
                billing_with_card = CustomerBillingAddress.objects.filter(user=user, is_old=True, is_deleted=False).first()
                if billing_with_card and billing_with_card.old_card:
                    try:
                        card_info = json.loads(billing_with_card.old_card.replace("'", "\""))
                        payment_details.card_last4 = card_info.get('last4', 'N/A')
                    except (json.JSONDecodeError, AttributeError):
                        payment_details.card_last4 = 'N/A'
                else:
                    payment_details.card_last4 = 'N/A'
        elif payment and payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment and payment_method == "cod":
            payment_details = CODPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment and payment_method == "bank_transfer":
            payment_details = BankTransferPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        items = []
        for order_item in order.items.all():
            product_image = order_item.product.main_image[0] if order_item.product.main_image else None
            items.append({
                'product': order_item.product,
                'quantity': order_item.quantity,
                'sku': order_item.product.supplier_sku,
                'total_price': order_item.price * order_item.quantity,
                'image_url': request.build_absolute_uri(product_image.image.url) if product_image else None,
            })

        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        max_delivery_days = max((item.product.delivery_time or 5) for item in order.items.all()) if order.items.exists() else 5
        estimated_delivery = order.created_at.date() + timedelta(days=max_delivery_days)

        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        context = {
            'order': order,
            'items': items,
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'total': total,
            },
            'order_total': total,
            'order_date': order.created_at,
            'billing': billing,
            'estimated_delivery': estimated_delivery,
            'payment_method': payment_method,
            'payment_details': payment_details,
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        }

        html_string = render_to_string('userdashboard/view/order_receipt_pdf.html', context)
        result = BytesIO()
        pdf = pisa.CreatePDF(src=html_string, dest=result)
        if pdf.err:
            logger.error(f"Failed to generate PDF for order {order.order_id}: {pdf.err}")
            return Response({"error": "Error generating PDF"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="order_receipt_{order.order_id}.pdf"'
        response.write(result.getvalue())
        logger.info(f"Generated PDF receipt for order {order.order_id} and user {user.id}")
        return response


class RFQSubmissionAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Log the incoming request data for debugging
        logger.debug(f"Request data: {request.data}, Content-Type: {request.content_type}")

        # Handle both JSON and form-data
        data = request.data if request.content_type == 'application/json' else request.POST

        product_id = data.get('product_id')
        if not product_id:
            logger.error(f"Product ID missing in request for user {request.user.id}")
            return Response({"error": {"product_id": ["This field is required."]}}, status=status.HTTP_400_BAD_REQUEST)
    



class CartListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart_items = CartProduct.objects.filter(user=request.user).select_related('product')
        serializer = CartProductSerializer(cart_items, many=True)

        subtotal = sum(float(item.product.price) * item.quantity for item in cart_items)
        shipping = 0.0 
        vat = 0.0
        total = round(subtotal + shipping + vat, 2)

        cart_summary = {
            "title": "Price Details",
            "Subtotal": subtotal,
            "Shipping": shipping,
            "VAT": vat,
            "Total": total
        }

        response_data = {
            "code": 200,
            "cart_summary": cart_summary,
            "message": "Success",
            "items": {
                "data": serializer.data
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

class CartAddAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))

        if not product_id:
            return format_response(data=None, message="Product ID is required", code=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, id=product_id)
        cart_item, created = CartProduct.objects.get_or_create(user=request.user, product=product)

        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity

        cart_item.save()
        return format_response(message="Product added to cart")

class CartRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        item_id = request.data.get('item_id')

        if not item_id:
            return format_response(data=None, message="Item ID is required", code=status.HTTP_400_BAD_REQUEST)

        try:
            item = CartProduct.objects.get(product_id=item_id, user=request.user)
            item.delete()
            return format_response(message="Item removed from cart")
        except CartProduct.DoesNotExist:
            return format_response(data=None, message="Item not found", code=status.HTTP_404_NOT_FOUND)
        
class WishlistToggleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return format_response(data=None, message="Product ID is required", code=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return format_response(data=None, message="Product not found", code=status.HTTP_404_NOT_FOUND)

        wishlist_item, created = WishlistProduct.objects.get_or_create(user=request.user, product=product)
        if not created:
            wishlist_item.delete()
            return format_response(data={"status": "removed"}, message="Removed from wishlist")
        return format_response(data={"status": "added"}, message="Added to wishlist")




class UserQuotationAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        sent_quotations = RFQRequest.objects.filter(quoted_by=user)
        received_quotations = RFQRequest.objects.filter(requested_by=user)

        serializer_context = {'request': request}
        data = {
            'sent_quotations': RFQRequestSerializer(sent_quotations, many=True, context=serializer_context).data,
            'received_quotations': RFQRequestSerializer(received_quotations, many=True, context=serializer_context).data
        }

        logger.info(f"Quotations loaded for user {user.id}: {sent_quotations.count()} sent, {received_quotations.count()} received")
        return Response(data)

 


class WishlistRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get("product_id")

        if not product_id:
            return format_response(message="Product ID is required", code=status.HTTP_400_BAD_REQUEST)

        try:
            wishlist_item = WishlistProduct.objects.get(user=request.user, product_id=product_id)
            wishlist_item.delete()
            return format_response(message="Product removed from wishlist")
        except WishlistProduct.DoesNotExist:
            return format_response(message="Product not found in wishlist", code=status.HTTP_404_NOT_FOUND)

class WishlistListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    @property
    def paginator(self):
        if not hasattr(self, '_paginator'):
            self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

    def get(self, request):
        wishlist_items = WishlistProduct.objects.filter(user=request.user).select_related('product')
        no_page = request.query_params.get('no_page', '').lower() in ('true', '1')

        if no_page:
            serializer = WishlistProductSerializer(wishlist_items, many=True)
            return format_response(data=serializer.data)

        page = self.paginate_queryset(wishlist_items)
        if page is not None:
            serializer = WishlistProductSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = WishlistProductSerializer(wishlist_items, many=True)
        return format_response(data=serializer.data)

class ShippingInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Profile detection
        phone = None
        profile_type = None
        try:
            profile = RetailProfile.objects.get(user=user)
            phone = profile.phone
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                phone = profile.phone
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    phone = profile.phone
                    profile_type = 'supplier'
                except SupplierProfile.DoesNotExist:
                    pass

        # Address info
        addresses = CustomerBillingAddress.objects.filter(user=user, is_deleted=False)
        default_address = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        # Cart info
        cart_items = CartProduct.objects.filter(user=user).select_related('product')
        subtotal = sum(Decimal(item.product.price) * item.quantity for item in cart_items)
        shipping = Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        data = {
           
            'addresses': CustomerBillingAddressSerializer(addresses, many=True).data,
            'default_address': CustomerBillingAddressSerializer(default_address).data if default_address else None,
            'cart_items': CartProductSerializer(cart_items, many=True).data,
            'order_summary': {
                'subtotal': str(subtotal),
                'shipping': str(shipping),
                'vat': str(vat),
                'total': str(total)
            }
        }

        return Response(data)


class RFQActionAPIView(views.APIView):
    permission_classes = [IsAuthenticated]
    action = None
    success_message = ""

    def post(self, request, pk):
        try:
            rfq = RFQRequest.objects.get(pk=pk, requested_by=request.user)
        except RFQRequest.DoesNotExist:
            logger.error(f"RFQ {pk} not found for user {request.user.id}")
            return Response({"error": "Quotation not found or you don't have permission to act on it."}, status=status.HTTP_404_NOT_FOUND)

        if rfq.status != 'quoted':
            logger.warning(f"RFQ {pk} status is {rfq.status}, not 'quoted', for user {request.user.id}")
            return Response({"error": "This quotation is not available for action."}, status=status.HTTP_400_BAD_REQUEST)

        rfq.status = self.action
        rfq.updated_at = timezone.now()
        rfq.save()

        logger.info(f"RFQ {pk} {self.action} by user {request.user.id}")
        return Response({"message": self.success_message}, status=status.HTTP_200_OK)


class RFQAcceptAPIView(RFQActionAPIView):
    action = 'accepted'
    success_message = "You have accepted the quotation."


class RFQRejectAPIView(RFQActionAPIView):
    action = 'rejected'
    success_message = "You have rejected the quotation."


class RequestRoleAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.debug(f"Request data: {request.data}, Content-Type: {request.content_type}")

        data = request.data if request.content_type == 'application/json' else request.POST
        files = request.FILES if request.content_type != 'application/json' else request.data

        requested_role = data.get('requested_role', 'retailer')
        valid_roles = [choice[0] for choice in RoleRequest.ROLE_CHOICES]
        if requested_role not in valid_roles:
            logger.error(f"Invalid role {requested_role} requested by user {request.user.id}")
            return Response({"error": f"Invalid role. Must be one of: {', '.join(valid_roles)}"}, status=status.HTTP_400_BAD_REQUEST)

        if RoleRequest.objects.filter(user=request.user, requested_role=requested_role).exists():
            logger.warning(f"User {request.user.id} already has a pending or approved request for role {requested_role}")
            return Response({"error": f"You already have a pending or approved request for {requested_role}."}, status=status.HTTP_400_BAD_REQUEST)

        if requested_role == 'retailer':
            serializer_class = RetailProfileSerializer
        elif requested_role == 'wholesaler':
            serializer_class = WholesaleBuyerProfileSerializer
        elif requested_role == 'supplier':
            serializer_class = SupplierProfileSerializer
        else:
            serializer_class = RetailProfileSerializer

        serializer = serializer_class(data=data, context={'request': request})
        if serializer.is_valid():
            role_request = RoleRequest.objects.create(
                user=request.user,
                requested_role=requested_role,
                status='pending'
            )

            profile_data = serializer.validated_data
            profile_data['user'] = request.user

            if requested_role == 'retailer':
                RetailProfile.objects.update_or_create(
                    user=request.user,
                    defaults=profile_data
                )
            elif requested_role == 'wholesaler':
                WholesaleBuyerProfile.objects.update_or_create(
                    user=request.user,
                    defaults=profile_data
                )
            elif requested_role == 'supplier':
                SupplierProfile.objects.update_or_create(
                    user=request.user,
                    defaults=profile_data
                )

            logger.info(f"Role request for {requested_role} submitted by user {request.user.id}")
            return Response({
                "message": f"Your role request for {requested_role} has been submitted.",
                "role_request": RoleRequestSerializer(role_request, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Role request submission failed for user {request.user.id}: {serializer.errors}")
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        role_choices = dict(RoleRequest.ROLE_CHOICES)
        selected_role = request.query_params.get('requested_role', 'retailer')
        if selected_role not in role_choices:
            selected_role = 'retailer'
        return Response({
            "role_choices": role_choices,
            "selected_role": selected_role
        }, status=status.HTTP_200_OK)

class ManageRequestsAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        role_requests = RoleRequest.objects.all().select_related('user')
        serializer_context = {'request': request}
        data = RoleRequestSerializer(role_requests, many=True, context=serializer_context).data
        logger.info(f"Role requests loaded for admin user {request.user.id}")
        return Response({"requests": data}, status=status.HTTP_200_OK)

class ApproveRoleRequestAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        try:
            role_request = RoleRequest.objects.get(pk=pk)
        except RoleRequest.DoesNotExist:
            logger.error(f"Role request {pk} not found for admin user {request.user.id}")
            return Response({"error": "Role request not found."}, status=status.HTTP_404_NOT_FOUND)

        user = role_request.user
        current_status = role_request.status
        action = request.data.get('action', 'approve')  # Default to approve

        if action == 'approve' and current_status == 'pending':
            role_request.status = 'approved'
            role_request.save()

            try:
                if role_request.requested_role == 'supplier':
                    supplier_profile, _ = SupplierProfile.objects.get_or_create(user=user)
                    logger.info(f"Verified SupplierProfile for {user.username}")
                elif role_request.requested_role == 'wholesaler':
                    wholesale_profile, _ = WholesaleBuyerProfile.objects.get_or_create(user=user)
                    logger.info(f"Verified WholesaleBuyerProfile for {user.username}")
                elif role_request.requested_role == 'retailer':
                    retail_profile, _ = RetailProfile.objects.get_or_create(user=user)
                    logger.info(f"Verified RetailProfile for {user.username}")
            except Exception as e:
                logger.error(f"Failed to verify profile for {user.username}: {str(e)}")
                return Response({"error": f"Failed to verify profile: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

            # Send acceptance email
            subject = 'Role Request Approved'
            html_message = render_to_string('userdashboard/email/role_approved.html', {
                'user': user.username,
                'role': role_request.requested_role,
                'date': '03:09 PM IST on Tuesday, August 05, 2025'
            })
            plain_message = strip_tags(html_message)
            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                logger.info(f"Email sent to {user.email} for role approval")
            except Exception as e:
                logger.error(f"Email sending failed for {user.email}: {str(e)}")
                return Response({
                    "message": f"Role '{role_request.requested_role}' approved for {user.username}, but email failed to send."
                }, status=status.HTTP_200_OK)

            logger.info(f"Role '{role_request.requested_role}' approved for {user.username} by admin {request.user.id}")
            return Response({
                "message": f"Role '{role_request.requested_role}' approved for {user.username}."
            }, status=status.HTTP_200_OK)

        elif action == 'reject' and current_status == 'approved':
            role_request.status = 'rejected'
            role_request.save()

            # Send rejection email
            subject = 'Role Request Rejected'
            html_message = render_to_string('userdashboard/email/role_rejected.html', {
                'user': user.username,
                'role': role_request.requested_role,
                'date': '03:09 PM IST on Tuesday, August 05, 2025'
            })
            plain_message = strip_tags(html_message)
            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                logger.info(f"Email sent to {user.email} for role rejection")
            except Exception as e:
                logger.error(f"Email sending failed for {user.email}: {str(e)}")
                return Response({
                    "message": f"Role request for {user.username} rejected, but email failed to send."
                }, status=status.HTTP_200_OK)

            logger.info(f"Role request for {user.username} rejected by admin {request.user.id}")
            return Response({
                "message": f"Role request for {user.username} rejected."
            }, status=status.HTTP_200_OK)

        else:
            logger.warning(f"Invalid action {action} or status {current_status} for role request {pk} by admin {request.user.id}")
            return Response({"error": "Invalid action or request status."}, status=status.HTTP_400_BAD_REQUEST)

       
        phone = None
        profile_type = None
        try:
            profile = RetailProfile.objects.get(user=user)
            phone = profile.phone
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                phone = profile.phone
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    phone = profile.phone
                    profile_type = 'supplier'
                except SupplierProfile.DoesNotExist:
                    pass

        
        addresses = CustomerBillingAddress.objects.filter(user=user, is_deleted=False)
        default_address = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()
        cart_items = CartProduct.objects.filter(user=user).select_related('product')
        subtotal = sum(Decimal(item.product.price) * item.quantity for item in cart_items)
        shipping = Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        data = {
           
            'addresses': CustomerBillingAddressSerializer(addresses, many=True).data,
            'default_address': CustomerBillingAddressSerializer(default_address).data if default_address else None,
            'cart_items': CartProductSerializer(cart_items, many=True).data,
            'order_summary': {
                'subtotal': str(subtotal),
                'shipping': str(shipping),
                'vat': str(vat),
                'total': str(total)
            }
        }

        return Response(data)

class AddAddressAPIView(generics.CreateAPIView):
    serializer_class = CustomerBillingAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        is_default = serializer.validated_data.get('is_default', False)
        if is_default:
            CustomerBillingAddress.objects.filter(user=user, is_default=True).update(is_default=False)
        serializer.save(user=user)

class RemoveAddressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, address_id):
        try:
            address = CustomerBillingAddress.objects.get(id=address_id, user=request.user, is_deleted=False)
            address.is_deleted = True
            address.save()
            return Response({'message': 'Address deleted successfully'}, status=status.HTTP_200_OK)
        except CustomerBillingAddress.DoesNotExist:
            return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)

class EditAddressAPIView(generics.UpdateAPIView):
    serializer_class = CustomerBillingAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomerBillingAddress.objects.filter(user=self.request.user, is_deleted=False)

    def perform_update(self, serializer):
        address = serializer.save()
        if address.is_default:
            CustomerBillingAddress.objects.filter(user=self.request.user, is_default=True).exclude(id=address.id).update(is_default=False)

class ProductSearchAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        search_query = request.GET.get('search', '').strip()
        sort_by = request.GET.get('sort_by') 

      
        effective_price = ExpressionWrapper(
            F('price') * (1 - F('offer_percentage') / 100.0),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )

        products = Product.objects.annotate(
            effective_price=Case(
                When(offer_active=True, offer_percentage__isnull=False, then=effective_price),
                default=F('price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).filter(is_active=True)

        if search_query:
            
            category = ProductCategory.objects.filter(name__icontains=search_query).first()
            if category:
                last_category_ids = ProductLastCategory.objects.filter(
                    sub_category__category=category
                ).values_list('id', flat=True)

                products = products.filter(last_category_id__in=last_category_ids)
            else:
               
                search_terms = search_query.lower().split()
                q_obj = Q()
                for term in search_terms:
                    q_obj |= Q(name__icontains=term) | Q(keywords__icontains=term)
                products = products.filter(q_obj)

        # Sorting
        if sort_by == '1':
            products = products.order_by('-effective_price')
        elif sort_by == '2':
            products = products.order_by('effective_price')
        else:
            products = products.order_by('-created_at')

        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = 16
        result_page = paginator.paginate_queryset(products, request)
        serializer = ProductSerializer(result_page, many=True)

        return paginator.get_paginated_response(serializer.data)
    
class WholesaleRegisterAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request, format=None):
        serializer = WholesaleRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "message": "Wholesale user registered successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            "success": False,
            "message": "Registration failed",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class SupplierRegisterAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = SupplierRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Supplier registered successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class WholesaleBuyerProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            profile = user.wholesalebuyerprofile
            profile_serializer = WholesaleBuyerProfileSerializer(profile)

            combined_data = {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                **profile_serializer.data
            }

            return Response({
                "code": 200,
                "message": "Success",
                "items": {
                    "data": combined_data
                }
            }, status=status.HTTP_200_OK)
        except AttributeError:
            return Response({
                "code": 404,
                "message": "Wholesale Buyer profile not found",
                "items": {
                    "data": None
                }
            }, status=status.HTTP_404_NOT_FOUND)

    def put(self, request):
        user = request.user
        try:
            profile = user.wholesalebuyerprofile
            serializer = WholesaleBuyerProfileSerializer(profile, data=request.data, partial=True)

            # Update User fields
            user_fields = ['username', 'email', 'first_name', 'last_name']
            user_updated = False
            for field in user_fields:
                if field in request.data:
                    setattr(user, field, request.data[field])
                    user_updated = True
            if user_updated:
                user.save()

            if serializer.is_valid():
                serializer.save()

                combined_data = {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    **serializer.data
                }

                return Response({
                    "code": 200,
                    "message": "Success",
                    "items": {
                        "data": combined_data
                    }
                }, status=status.HTTP_200_OK)

            return Response({
                "code": 400,
                "message": "Failed",
                "items": {
                    "data": serializer.errors
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        except AttributeError:
            return Response({
                "code": 404,
                "message": "Wholesale Buyer profile not found",
                "items": {
                    "data": None
                }
            }, status=status.HTTP_404_NOT_FOUND)



class SupplierProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            profile = user.supplierprofile
        except SupplierProfile.DoesNotExist:
            return Response({
                "code": 404,
                "message": "Supplier profile not found",
                "items": None
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = SupplierProfileSerializer(profile)

        combined_data = {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            **serializer.data
        }

        return Response({
            "code": 200,
            "message": "Success",
            "items": {
                "data": combined_data
            }
        }, status=status.HTTP_200_OK)

    def put(self, request):
        user = request.user
        try:
            profile = user.supplierprofile
        except SupplierProfile.DoesNotExist:
            return Response({
                "code": 404,
                "message": "Supplier profile not found",
                "items": None
            }, status=status.HTTP_404_NOT_FOUND)

 
        serializer = SupplierProfileSerializer(profile, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            user_fields = ["username", "email", "first_name", "last_name"]
            user_data_updated = False
            for field in user_fields:
                if field in request.data:
                    setattr(user, field, request.data[field])
                    user_data_updated = True

            if user_data_updated:
                user.save()

            combined_data = {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                **serializer.data
            }

            return Response({
                "code": 200,
                "message": "Profile Updated Successfully",
                "items": {
                    "data": combined_data
                }
            }, status=status.HTTP_200_OK)

        return Response({
            "code": 400,
            "message": "Validation failed",
            "items": {
                "errors": serializer.errors
            }
        }, status=status.HTTP_400_BAD_REQUEST)
