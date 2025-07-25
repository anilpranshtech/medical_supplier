from django.contrib.auth import authenticate
from django.shortcuts import render, get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth.models import User
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import viewsets, status, response, permissions, mixins
from django.utils.timezone import now
from dashboard.models import PasswordUpdateTracker
from medical_api.serializers import UserLoginSerializer, DoctorRegistrationSerializer, ChangePasswordSerializer, \
    DoctorProfileSerializer
from django.contrib.auth import get_user_model, login, authenticate, logout
from rest_framework.response import Response

UserModel = get_user_model()


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



class DoctorProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.doctor_profile
        serializer = DoctorProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        profile = request.user.doctor_profile
        serializer = DoctorProfileSerializer(profile, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
