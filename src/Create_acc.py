import streamlit as st
import boto3
from Demos.win32cred_demo import domain
from pyasn1_modules.rfc2459 import emailAddress
from streamlit_cognito_auth import CognitoAuthenticator

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
region = 'us-east-2'

cognito = boto3.client('cognito-idp', region_name=region)

def user_acc(username, password):
    try:
        response = cognito.sign_up(
            Client_id=client_id,
            Username=username,
            Password=password,
            UserAttributes=[
                {'Name': 'email', 'Value': emailAddress}
            ]
        )
        return response

    except cognito.exceptions.UsernameExistsException:
        st.error("Username already exists")
        return None
    except Exception as e:
        st.error(str(e))
        return None

def register_page():
    st.subheader("Create a New Account")

    username = st.text_input("Choose a Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")

    if st.button("Register"):
        if password != confirm_password:
            st.error("Passwords do not match!")
        else:
            response = register_user(username, password, email)
            if response:
                st.success("Account created successfully! Please check your email for a verification link.")
                st.session_state.page = 'login'

    if st.button("Back to Login"):
        st.session_state.page = 'login'