import stripe
import logging
import traceback
from datetime import datetime
from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import (UserCardsAndSubscriptions,CustomerPayment,StripeSubscriptions,)
logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    def get_active_subscription_offer(self):
        return None
    def get_credits_for_plan(self, price_id):
        """Get credits from StripeSubscriptions plans"""
        plan = StripeSubscriptions.objects.filter(price_id=price_id).first()
        if plan:
            return plan.nm_credits
        return 0
    def get_plan_duration(self, price_id):
        plan = StripeSubscriptions.objects.filter(price_id=price_id).first()
        if plan:
            return plan.plan_duration
        return StripeSubscriptions.PlanDuration.MONTH
    def is_custom_subscription(self, price_id):
        return False
    def post(self, request, *args, **kwargs):
        try:
            payload = request.body
            sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
            
            logger.info(f"🔔 WEBHOOK RECEIVED: {request.method} {request.path}")
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, endpoint_secret
                )
            except (ValueError, stripe.error.SignatureVerificationError) as e:
                logger.error(f"❌ WEBHOOK SIGNATURE VERIFICATION FAILED: {e}")
                return HttpResponse(status=400)
            
            event_type = event['type']
            data = event['data']['object']
            
            logger.info(f"🎯 EVENT TYPE: {event_type}")
            logger.info(f"👤 CUSTOMER ID: {data.get('customer')}")
            
            customer_id = data.get('customer')
            if not customer_id:
                logger.warning("❌ NO CUSTOMER ID")
                return HttpResponse(status=200)
            try:
                user_profile = UserCardsAndSubscriptions.objects.get(
                    stripe_customer_id=customer_id
                )
                user = user_profile.user
                logger.info(f"✅ USER FOUND: {user.username}")
            except UserCardsAndSubscriptions.DoesNotExist:
                logger.error(f"❌ USER NOT FOUND for customer_id: {customer_id}")
                return HttpResponse(status=200)
            if event_type == 'invoice.payment_succeeded':
                subscription_id = data.get("subscription")
                billing_reason = data.get("billing_reason")
                amount_paid = data.get("amount_paid", 0) / 100
                charge_id = data.get("charge", "")
                
                logger.info(f"💳 PAYMENT SUCCEEDED:")
                logger.info(f"   Subscription ID: {subscription_id}")
                logger.info(f"   Billing Reason: {billing_reason}")
                logger.info(f"   Amount: ${amount_paid}")
                
                if not subscription_id:
                    logger.warning("❌ NO SUBSCRIPTION ID")
                    return HttpResponse(status=200)
                subscription_obj = stripe.Subscription.retrieve(subscription_id)
                subscription_price_id = subscription_obj['items']['data'][0]['price']['id']
                credits_for_plan = self.get_credits_for_plan(subscription_price_id)
                current_price_id = user_profile.active_subscription_price_id
                price_obj = stripe.Price.retrieve(subscription_price_id)
                product_obj = stripe.Product.retrieve(price_obj['product'])
                plan_name = product_obj['name']
                
                old_plan_name = "No Previous Plan"
                if current_price_id:
                    try:
                        old_price_obj = stripe.Price.retrieve(current_price_id)
                        old_product_obj = stripe.Product.retrieve(old_price_obj['product'])
                        old_plan_name = old_product_obj['name']
                    except:
                        pass
                if current_price_id and current_price_id != subscription_price_id:
                    try:
                        current_amount = stripe.Price.retrieve(current_price_id).unit_amount
                        new_amount = stripe.Price.retrieve(subscription_price_id).unit_amount
                        
                        current_credits = self.get_credits_for_plan(current_price_id)
                        new_credits = self.get_credits_for_plan(subscription_price_id)
                        if new_amount > current_amount and new_credits > current_credits:
                            current_remaining = user_profile.subscriptions_credits_number_checks
                            used_credits = current_credits - current_remaining
                            final_credits = max(0, new_credits - used_credits)
                        else:
                            final_credits = new_credits
                    except:
                        final_credits = credits_for_plan
                    plan_duration = self.get_plan_duration(subscription_price_id)
                    period_start = datetime.fromtimestamp(subscription_obj['current_period_start'])
                    period_end = datetime.fromtimestamp(subscription_obj['current_period_end'])
                    
                    user_profile.active_subscription_price_id = subscription_price_id
                    user_profile.subscriptions_credits_number_checks = final_credits
                    user_profile.subscription_status = 'active'
                    user_profile.stripe_subscription_id = subscription_id
                    user_profile.plan_duration = plan_duration
                    user_profile.subscriptions_period_start = period_start
                    user_profile.subscriptions_period_end = period_end
                    user_profile.save()
                    
                    logger.info(f"✅ PLAN CHANGED: {old_plan_name} → {plan_name}")
                    logger.info(f"   Credits updated to: {final_credits}")
                    
                else:
                    user_profile.subscriptions_offer_credits_number_checks = 0
                    
                    plan_duration = self.get_plan_duration(subscription_price_id)
                    
                    period_start = datetime.fromtimestamp(subscription_obj['current_period_start'])
                    period_end = datetime.fromtimestamp(subscription_obj['current_period_end'])
                    
                    user_profile.active_subscription_price_id = subscription_price_id
                    user_profile.subscriptions_credits_number_checks = credits_for_plan
                    user_profile.subscription_status = 'active'
                    user_profile.stripe_subscription_id = subscription_id
                    user_profile.plan_duration = plan_duration
                    user_profile.subscriptions_period_start = period_start
                    user_profile.subscriptions_period_end = period_end
                    user_profile.save()
                    
                    logger.info(f"✅ SUBSCRIPTION ACTIVE: {plan_name}")
                    logger.info(f"   Credits: {credits_for_plan}")
                CustomerPayment.objects.create(
                    user=user,
                    stripe_charge_id=charge_id,
                    amount=int(amount_paid),
                    is_subscription=True,
                )
                
                logger.info(f"✅ PAYMENT RECORD CREATED")
            elif event_type == 'customer.subscription.deleted':
                logger.info(f"🗑️ SUBSCRIPTION DELETED")
                
                UserCardsAndSubscriptions.objects.filter(
                    stripe_customer_id=customer_id
                ).update(
                    stripe_subscription_id=None,
                    active_subscription_price_id=None,
                    subscription_status="canceled",
                    subscriptions_credits_number_checks=0,
                    subscriptions_offer_credits_number_checks=0,
                    subscriptions_period_start=None,
                    subscriptions_period_end=None,
                    last_credit_reset_date=None
                )
                
                logger.info(f"✅ SUBSCRIPTION CLEANED UP")
            else:
                logger.info(f"ℹ️ Unhandled event type: {event_type}")
            
            return HttpResponse(status=200)
        
        except Exception as e:
            logger.error(f"❌ WEBHOOK ERROR: {str(e)}")
            logger.error(f"❌ TRACEBACK: {traceback.format_exc()}")
            return HttpResponse(status=200)