import streamlit as st
import boto3

from HASystem.src.Create_acc import register_page

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
region = 'us-east-2'

cognito = boto3.client('cognito-idp', region_name=region)
def auth_user(username, password):
    try:
        response = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={'USERNAME': username, 'PASSWORD': password}
        )
        return response['AuthenticationResult']
    except cognito.exceptions.NotAuthorizedException:
        st.error('Invalid Username or password.')
        return None
    except Exception as e:
        st.error(str(e))
        return None

def login_page():
    st.subheader('Login')

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')

        col1, col2 = st.columns(2)
        with col1:
            if st.button('Login'):
                auth_result = auth_user(username, password)
                if auth_result:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success("Login Complete")
        with col2:
            if st.button('Create Account'):
                st.session_state.page = 'register'

    else:
        st.write("Welcome, **{}st.session_state.username**!")
        st.write("This is a temporary page")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.success("Logged out")

def main():
    st.title('Cloud Drive')

    if 'page' not in st.session_state:
        st.session_state.page = 'login'

    if st.session_state.page == 'login':
        login_page()
    elif st.session_state.page == 'register':
        register_page()

if __name__ == '__main__':
            main()