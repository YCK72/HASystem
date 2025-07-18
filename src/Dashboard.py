import streamlit as st
import boto3

def dashboard_page():
    st.title('Cloud Drive')
    st.write(f"You are logged in as **{st.session_state.username}**.")
    st.write("We did not do much come again later.")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.page = 'login'