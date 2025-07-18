import streamlit as st
import boto3

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
region = 'us-east-2'

cognito = boto3.client('cognito-idp', region_name=region)

def verify_otp(email, code):
    try:
        response = cognito.confirm_sign_up(
            ClientId=client_id,
            Username=email,
            ConfirmationCode=code
        )
        return response
    except cognito.exceptions.CodeMismatchException:
        st.error("Invalid OTP. Please try again.")
        return None
    except cognito.exceptions.ExpiredCodeException:
        st.error("OTP has expired. Please request a new one.")
        return None
    except Exception as e:
        st.error(str(e))
        return None

