import requests

def send_phone_otp(input_value, token):
    url = 'https://api.textdrip.com/api/v1/email-otp'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    payload = {
        "input": input_value,
        "input_type": 'mobile',
        "platform": "Medical Supplier"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        print(input_value, type(input_value), payload)
        print(response.json())
        return response.json()
    except requests.exceptions.RequestException as e:
        # Log the error or handle it as needed
        return {"error": str(e)}


def verify_mobile_otp(api_url, token, mobile_number, otp):
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    payload = {
        'input': mobile_number,
        'input_type': 'mobile',
        'otp': otp,
    }
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        print("VERIFICATION REQUEST:", payload)
        print("VERIFICATION RESPONSE:", response.json())
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}