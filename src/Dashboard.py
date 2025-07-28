import streamlit as st
import boto3
import base64
import json

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
identity_pool_id = 'us-east-2:254bd728-cb37-4779-9cb0-bcb0a4b1c2b1'
region = 'us-east-2'
bucket_name = 'myawsbucket1212398'

identityClient = boto3.client('cognito-identity', region_name=region)
s3Client = None

def authorize_user():
    response = identityClient.get_id(
            IdentityPoolId=identity_pool_id,
            Logins={
            f"cognito-idp.{region}.amazonaws.com/{user_pool_id}": st.session_state.IdToken
            }
        )
    identityId = response['IdentityId']
    if not identityId:
        st.warning("User is not authorized for this application")
        return
    st.session_state.IdentityId = identityId

def getBucketFolder():
    rawpayload = base64.b64decode(st.session_state.IdToken.split(".")[1]+'==')

    parsedPayload = rawpayload.decode('utf-8')
    payload_dict = json.loads(parsedPayload)
    
    userfolder = payload_dict['sub']
    return f'private/{userfolder}/'

def authenticate_s3():
    global s3Client

    # check if identity id exists
    if 'IdentityId' not in st.session_state:
        authorize_user()

    # get access tokens to connect to s3 client
    response = identityClient.get_credentials_for_identity(
        IdentityId=st.session_state.IdentityId,
        Logins={
                f"cognito-idp.{region}.amazonaws.com/{user_pool_id}": st.session_state.IdToken
                }
            )
    
    credentials = response['Credentials']
    if not credentials:
        st.warning("failed to assign credentials for this user")
        return
    
    access_key_id = credentials['AccessKeyId']
    secret_access_key  = credentials['SecretKey']
    session_token = credentials['SessionToken']

    session =boto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=session_token,
        region_name=region
    )

    s3Client = session.client('s3')

    

def dashboard_page():
    authenticate_s3()

    st.title('Cloud Drive')
    st.write(f"You are logged in as **{st.session_state.username}**.")

    folderPrefix = getBucketFolder()

    files = s3Client.list_objects_v2(Bucket=bucket_name)
    files = [x['Key'] for x in files['Contents'] if x['Key'].startswith(folderPrefix)]
    
    with st.container():
        for f in files:
            st.write(f)


    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.page = 'login'

    if st.button("upload"):
        uploaded_file = st.file_uploader("choose file",type=None)

        if uploaded_file is not None:
            s3Client.upload_fileobj(uploaded_file,bucket_name,folderPrefix+uploaded_file.name)
            st.success(f"File '{uploaded_file.name}' uploaded to {bucket_name}")