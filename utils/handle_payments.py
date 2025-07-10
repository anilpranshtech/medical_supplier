import stripe
import logging
logger = logging.getLogger(__name__)

def ChargeUser(customer_id, charge_amount,payment_descriptions='Not Found'):
    try:
        decimal_int = charge_amount * 100
        final_amount = int(decimal_int)
        decimal_charge_amt = final_amount
        charge = stripe.Charge.create(
            amount=decimal_charge_amt,
            currency="usd",
            customer=customer_id,
            description=payment_descriptions
        )
        return charge
    except Exception as e:
        error_message = f"Stripe Charge Error: {str(e)}"
        logger.error(error_message)
        print(error_message)
        return None


def ChargeUserInTestMode(customer_id, charge_amount, payment_descriptions):
    """
    Simulate a test mode charge.
    """
    try:
        decimal_int = charge_amount * 100
        final_amount = int(decimal_int)
        decimal_charge_amt = final_amount
        charge = stripe.Charge.create(
            amount=decimal_charge_amt,
            currency="usd",
            customer=customer_id,
            description=payment_descriptions
        )
        return charge
    except Exception as e:
        return None