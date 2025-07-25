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
    SupplierProfile
from medical_api.serializers import UserLoginSerializer, DoctorRegistrationSerializer, ChangePasswordSerializer, \
    DoctorProfileSerializer, ProductCategorySerializer, ProductSubCategorySerializer, ProductLastCategorySerializer, \
    ProductSerializer, ProductCreateSerializer, UserEmailSerializer, SupplierListSerializer, ResidencySerializer, \
    SpecialitySerializer, NationalitySerializer, CountryCodeSerializer
from django.contrib.auth import get_user_model, login, authenticate, logout
from rest_framework.response import Response

UserModel = get_user_model()
from dashboard.models import Residency, Speciality, Nationality, CountryCode
from django.conf import settings
import re


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class UserLoginAdminView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, format=None):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.data.get("email")
            password = serializer.data.get("password")
            user = authenticate(email=email, password=password)

            print(email)
            print(password)
            print(user)
            user_data = UserModel.objects.filter(email=email).last()
            if user is not None:
                login(request, user)
                token = get_tokens_for_user(user)
                token["status"] = True
                token["username"] = str(user)
                token["first_name"] = user.first_name
                token["last_name"] = user.last_name
                token["email"] = user.email

                if user.is_superuser:
                    token["account_role"] = 'Administrator'
                elif user.is_staff and user.is_active:
                    token["account_role"] = 'Staff'
                elif not user.is_staff and user.is_active:
                    token["account_role"] = 'User'

                if user.is_staff or user.is_superuser:
                    try:
                        try:
                            user_last_modified = PasswordUpdateTracker.objects.get(user=user)
                        except:
                            user_last_modified = PasswordUpdateTracker.objects.create(user=user,
                                                                                      last_password_update=user.date_joined)
                        if user_last_modified:
                            token['Update_password_required'] = user_last_modified.is_password_expired()
                        else:
                            token['Update_password_required'] = True

                    except PasswordUpdateTracker.DoesNotExist:
                        # If there's no tracker data for the user, decide how to handle it
                        token['Update_password_required'] = None

                return Response(
                    token,
                    status=status.HTTP_200_OK)
            else:
                return Response({"message": "Email or Password is not valid", "status": False},
                                status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"message": "Email or Password is not valid"}, status.HTTP_400_BAD_REQUEST)


class DoctorRegisterAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request, format=None):
        serializer = DoctorRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Registration successful'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user  # authenticated via token/session

        serializer = ChangePasswordSerializer(data=request.data, context={'user': user})

        if serializer.is_valid():
            serializer.change_password(user)

            if user.is_superuser and user.is_staff:
                PasswordUpdateTracker.objects.update_or_create(
                    user=user,
                    defaults={'last_password_update': now()}
                )

            return Response(
                {"email": user.email, "message": "Password updated successfully"},
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        except KeyError:
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        except TokenError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        email = request.data.get('email')
        User = get_user_model()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'No account found with this email.'}, status=400)

        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
        # send_mail(
        #     subject="Password Reset Request",
        #     message=f"Use the link below to reset your password:\n\n{reset_link}",
        #     from_email=settings.DEFAULT_FROM_EMAIL,
        #     recipient_list=[email],
        # )
        return Response({
            'message': 'Password reset credentials.',
            'token': token,
            'uid': uid
             })


class ResetPasswordAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request, uidb64, token):
        password = request.data.get('password')
        confirm_password = request.data.get('confirm_password')

        if not password or not confirm_password:
            return Response({'error': 'Password and confirm password are required.'}, status=400)

        if password != confirm_password:
            return Response({'error': 'Passwords do not match.'}, status=400)

        if len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters long.'}, status=400)
        if not re.search(r'[A-Z]', password):
            return Response({'error': 'Password must contain at least one uppercase letter.'}, status=400)
        if not re.search(r'[a-z]', password):
            return Response({'error': 'Password must contain at least one lowercase letter.'}, status=400)
        if not re.search(r'[0-9]', password):
            return Response({'error': 'Password must contain at least one number.'}, status=400)
        if not re.search(r'[\W_]', password):
            return Response({'error': 'Password must contain at least one special character.'}, status=400)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = get_user_model().objects.get(pk=uid)
        except Exception:
            return Response({'error': 'Invalid or expired link.'}, status=400)

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response({'error': 'Invalid or expired token.'}, status=400)

        user.set_password(password)
        user.save()
        return Response({'message': 'Password has been reset successfully.'}, status=status.HTTP_200_OK)
class DoctorProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.doctor_profile
        serializer = DoctorProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        profile = request.user.doctor_profile
        serializer = DoctorProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        categories = ProductCategory.objects.all()
        serializer = ProductCategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ProductCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Category created", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubCategoryListByCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response({'error': 'category_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        subcategories = ProductSubCategory.objects.filter(category_id=category_id)
        serializer = ProductSubCategorySerializer(subcategories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ProductSubCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Subcategory created", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LastCategoryListBySubCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub_category_id = request.query_params.get('sub_category_id')
        if not sub_category_id:
            return Response({'error': 'sub_category_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        last_categories = ProductLastCategory.objects.filter(sub_category_id=sub_category_id)
        serializer = ProductLastCategorySerializer(last_categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ProductLastCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Last category created", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProductListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class ProductDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'


class ProductCreateAPIView(CreateAPIView):

    serializer_class = ProductCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UserEmailViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserEmailSerializer
    permission_classes = [IsAuthenticated]

class SupplierList(viewsets.ReadOnlyModelViewSet):
    queryset = SupplierProfile.objects.all()
    serializer_class = SupplierListSerializer
    permission_classes = [IsAuthenticated]



class SpecialityListView(ListAPIView):
    serializer_class = SpecialitySerializer

    def get_queryset(self):
        return Speciality.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response({"message": "No specialties found", "data": []}, status=status.HTTP_200_OK)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"message": "Specialties fetched successfully", "data": serializer.data})


class ResidencyListView(ListAPIView):
    serializer_class = ResidencySerializer

    def get_queryset(self):
        return Residency.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response({"message": "No residencies found", "data": []}, status=status.HTTP_200_OK)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"message": "Residencies fetched successfully", "data": serializer.data})


class NationalityListView(ListAPIView):
    serializer_class = NationalitySerializer

    def get_queryset(self):
        return Nationality.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response({"message": "No nationalities found", "data": []}, status=status.HTTP_200_OK)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"message": "Nationalities fetched successfully", "data": serializer.data})


class CountryCodeListView(ListAPIView):
    serializer_class = CountryCodeSerializer

    def get_queryset(self):
        return CountryCode.objects.all()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response({"message": "No country codes found", "data": []}, status=status.HTTP_200_OK)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"message": "Country codes fetched successfully", "data": serializer.data})
