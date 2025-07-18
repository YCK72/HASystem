import streamlit as st
import boto3

from Create_acc import register_page
from verify_otp import verify_otp
from Dashboard import dashboard_page

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
region = 'us-east-2'

cognito = boto3.client('cognito-idp', region_name=region)
def auth_user(email, password):
    try:
        response = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={'EMAIL': email, 'PASSWORD': password}
        )
        return response['AuthenticationResult']
    except cognito.exceptions.NotAuthorizedException:
        st.error('Invalid Email or password.')
        return None
    except cognito.exceptions.UserNotConfirmedException:
        st.warning("Email is not verified. Check your email and try again.")
        st.session_state.pending_email = email
        st.session_state.page = 'verify_otp'
        return None
    except Exception as e:
        st.error(str(e))
        return None

def login_page():
    st.subheader('Login')

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        email = st.text_input('Email')
        password = st.text_input('Password', type='password')

        col1, col2 = st.columns(2)
        with col1:
            if st.button('Login'):
                auth_result = auth_user(email, password)
                if auth_result:
                    st.session_state.logged_in = True
                    st.session_state.username = email
                    st.success("Login Complete")
        with col2:
            if st.button('Create Account'):
                st.session_state.page = 'register'

    else:
        dashboard_page()


def verification_page():
    st.subheader("Authenticate your account")
    email = st.session_state.get("pending_email", "")

    if not email:
        st.warning("No email found. Enter valid email address in the registration page")
        if st.button("Go to Registration Page"):
            st.session_state.page = 'register'
        return

    st.write(f"An OTP was sent to: **{email}**")
    code = st.text_input("Enter the verification code from your email")

    if st.button("Verify OTP"):
        if not code:
            st.error("Please enter a verification code.")
        else:
            response = verify_otp(email, code)
            if response is not None:
                st.success("Account verification complete! You can now log in.")
                st.session_state.pending_email = None
                st.session_state.page = 'login'

        if st.button("Resend Code"):
            try:
                cognito._resend_confirmation_code(ClientId=client_id, Username=email)
                st.info("Code sent successfully")
            except Exception as e:
                st.error(str(e))

def main():
    st.title('Cloud Drive')

    if 'page' not in st.session_state:
        st.session_state.page = 'login'

    if st.session_state.page == 'login':
        login_page()
    elif st.session_state.page == 'register':
        register_page()
    elif st.session_state.page == 'verify_otp':
        verification_page()
    elif st.session_state.page == 'dashboard':
        dashboard_page()

if __name__ == '__main__':
            main()