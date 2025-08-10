# Login_page.py
import streamlit as st
import boto3

from Create_acc import register_page
from verify_otp import verify_otp
from Dashboard import dashboard_page

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
region = 'us-east-2'

cognito = boto3.client('cognito-idp', region_name=region)


def auth_user(email: str, password: str):
    try:
        response = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={'USERNAME': email, 'PASSWORD': password}
        )
        return response['AuthenticationResult']
    except cognito.exceptions.NotAuthorizedException:
        st.error('Invalid email or password.')
        return None
    except cognito.exceptions.UserNotConfirmedException:
        st.warning("Email not verified. Please enter the verification code sent to your email.")
        st.session_state.pending_email = email
        st.session_state.page = 'verify_otp'
        st.rerun()
        return None
    except Exception as e:
        st.error(str(e))
        return None


# ---------- UI pages ----------
def login_page():
    st.subheader('Login')

    # Initialize session keys if missing
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'page' not in st.session_state:
        st.session_state.page = 'login'

    if not st.session_state.logged_in:
        email = st.text_input('Email')
        password = st.text_input('Password', type='password')

        col1, col2 = st.columns(2)
        with col1:
            if st.button('Login', type="primary", use_container_width=True):
                if not email or not password:
                    st.error("Please provide both email and password.")
                else:
                    auth_result = auth_user(email, password)
                    if auth_result:
                        st.session_state.logged_in = True
                        st.session_state.username = email
                        st.session_state.IdToken = auth_result.get('IdToken')
                        st.session_state.page = 'dashboard'
                        st.success("Logged in successfully.")
                        st.rerun()

        with col2:
            if st.button('Create Account', use_container_width=True):
                st.session_state.page = 'register'
                st.rerun()
    else:
        # Already logged in -> go to dashboard
        st.session_state.page = 'dashboard'
        st.rerun()


def verification_page():
    st.subheader("Authenticate your account")

    email = st.session_state.get("pending_email", "")
    if not email:
        st.warning("No email found. Please register first.")
        if st.button("Go to Registration Page"):
            st.session_state.page = 'register'
            st.rerun()
        return

    st.write(f"An OTP was sent to: **{email}**")
    code = st.text_input("Enter the verification code from your email")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Verify OTP", type="primary", use_container_width=True):
            if not code:
                st.error("Please enter a verification code.")
            else:
                response = verify_otp(email, code)
                if response is not None:
                    st.success("Account verification complete! You can now log in.")
                    st.session_state.pending_email = None
                    st.session_state.page = 'login'
                    st.rerun()

    with col2:
        if st.button("Resend Code", use_container_width=True):
            try:
                # Use the public method (no underscore)
                cognito.resend_confirmation_code(ClientId=client_id, Username=email)
                st.info("Verification code resent successfully.")
            except Exception as e:
                st.error(str(e))

    with col3:
        if st.button("Back to Login", use_container_width=True):
            st.session_state.page = 'login'
            st.rerun()


def main():
    st.title('Cloud Drive')

    if 'page' not in st.session_state:
        st.session_state.page = 'login'

    page = st.session_state.page

    if page == 'login':
        login_page()
    elif page == 'register':
        register_page()
    elif page == 'verify_otp':
        verification_page()
    elif page == 'dashboard':
        dashboard_page()
    else:
        # Fallback to login
        st.session_state.page = 'login'
        st.rerun()

if __name__ == '__main__':
    main()
