from django.contrib.auth import authenticate
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.shortcuts import render, get_object_or_404
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth.models import User
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import viewsets, status, response, permissions, mixins, generics
from django.utils.timezone import now
from dashboard.models import PasswordUpdateTracker, ProductCategory, ProductSubCategory, ProductLastCategory, Product, \
    SupplierProfile,SubscriptionPlan, UserSubscription
from medical_api.serializers import UserLoginSerializer, DoctorRegistrationSerializer, ChangePasswordSerializer, \
    DoctorProfileSerializer, ProductCategorySerializer, ProductSubCategorySerializer, ProductLastCategorySerializer, \
    ProductSerializer, ProductCreateSerializer, UserEmailSerializer, SupplierListSerializer, ResidencySerializer, \
    SpecialitySerializer, NationalitySerializer, CountryCodeSerializer,SubscriptionPlanSerializer, UserSubscriptionSerializer
from django.contrib.auth import get_user_model, login, authenticate, logout
from rest_framework.response import Response

UserModel = get_user_model()
from dashboard.models import Residency, Speciality, Nationality, CountryCode
from django.conf import settings
import re
from rest_framework.pagination import PageNumberPagination

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