import streamlit as st
import boto3

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
region = 'us-east-2'

cognito = boto3.client('cognito-idp', region_name=region)

def user_acc(email, password):
    try:
        response = cognito.sign_up(
            ClientId=client_id,
            Username=email,
            Password=password,
            UserAttributes=[
                {'Name': 'email', 'Value': email}
            ]
        )
        return response

    except cognito.exceptions.UsernameExistsException:
        st.error("Account with this email already exists")
        return None
    except Exception as e:
        st.error(str(e))
        return None

def register_page():
    st.subheader("Create a New Account")

    #username = st.text_input("Choose a Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")

    if st.button("Register"):
        if password != confirm_password:
            st.error("Passwords do not match!")
        elif not email or not password:
            st.error("Please fill in all the fields")
        else:
            response = user_acc(email, password)
            if response:
                st.success("Account created successfully! Please check your email for a verification link.")
                st.session_state.pending_email = email
                st.session_state.page = 'verify_otp'

    if st.button("Back to Login"):
        st.session_state.page = 'login'
