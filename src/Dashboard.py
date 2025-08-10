# Dashboard.py
import streamlit as st
import boto3
import base64
import json
import mimetypes

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
identity_pool_id = 'us-east-2:254bd728-cb37-4779-9cb0-bcb0a4b1c2b1'
region = 'us-east-2'
bucket_name = 'myawsbucket1212398'

identityClient = boto3.client('cognito-identity', region_name=region)
s3Client = None


def authorize_user():
    try:
        response = identityClient.get_id(
            IdentityPoolId=identity_pool_id,
            Logins={
                f"cognito-idp.{region}.amazonaws.com/{user_pool_id}": st.session_state.IdToken
            }
        )
        identityId = response.get('IdentityId')
        if not identityId:
            st.warning("User is not authorized for this application")
            return
        st.session_state.IdentityId = identityId
    except Exception as e:
        st.error(f"Authorization failed: {e}")


def _decode_jwt_payload(id_token: str) -> dict:
    try:
        payload_part = id_token.split(".")[1]
        padding = "=" * (-len(payload_part) % 4)
        decoded = base64.urlsafe_b64decode(payload_part + padding).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return {}


def getBucketFolder():
    payload_dict = _decode_jwt_payload(st.session_state.IdToken)
    user_sub = payload_dict.get('sub')
    if not user_sub:
        st.warning("Unable to parse user ID from token; using fallback folder.")
        user_sub = "unknown"
    return f'private/{user_sub}/'


def authenticate_s3():
    global s3Client

    if 'IdentityId' not in st.session_state:
        authorize_user()

    try:
        response = identityClient.get_credentials_for_identity(
            IdentityId=st.session_state.IdentityId,
            Logins={
                f"cognito-idp.{region}.amazonaws.com/{user_pool_id}": st.session_state.IdToken
            }
        )
        credentials = response.get('Credentials')
        if not credentials:
            st.warning("Failed to assign credentials for this user")
            return

        session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretKey'],
            aws_session_token=credentials['SessionToken'],
            region_name=region
        )
        s3Client = session.client('s3')
    except Exception as e:
        st.error(f"S3 authentication failed: {e}")


def list_user_objects(prefix: str):
    try:
        resp = s3Client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        return [o for o in resp.get('Contents', []) if not o['Key'].endswith('/')]
    except Exception as e:
        st.error(f"Failed to list objects: {e}")
        return []


def render_file_list(objs):
    if not objs:
        st.info("No files found.")
        return

    for obj in objs:
        key = obj['Key']
        filename = key.split('/')[-1]

        left, right = st.columns([6, 2])
        with left:
            st.write(filename)
        with right:
            try:
                obj_resp = s3Client.get_object(Bucket=bucket_name, Key=key)
                file_bytes = obj_resp['Body'].read()
                st.download_button(
                    label="Download",
                    data=file_bytes,
                    file_name=filename,
                    mime="application/octet-stream",
                    key=f"dl_{key}"
                )
            except Exception as e:
                st.error(f"Download failed for {filename}: {e}")


def dashboard_page():
    authenticate_s3()
    if s3Client is None:
        st.stop()

    st.title('Cloud Drive')
    st.write(f"You are logged in as **{st.session_state.username}**.")

    folderPrefix = getBucketFolder()

    uploaded_file = st.file_uploader("Choose a file to upload", type=None)
    if uploaded_file is not None:
        try:
            content_type, _ = mimetypes.guess_type(uploaded_file.name)
            extra_args = {'ContentType': content_type} if content_type else {}
            s3Client.upload_fileobj(
                uploaded_file,
                bucket_name,
                folderPrefix + uploaded_file.name,
                ExtraArgs=extra_args
            )
            st.success(f"File '{uploaded_file.name}' uploaded to {bucket_name}")
        except Exception as e:
            st.error(f"Upload failed: {e}")

    st.divider()

    objects = list_user_objects(folderPrefix)
    render_file_list(objects)

    st.divider()
    if st.button("Refresh list"):
        st.experimental_rerun()

    if st.button("Logout"):
        for k in ['logged_in', 'username', 'IdToken', 'IdentityId', 'page']:
            st.session_state.pop(k, None)
        st.session_state.page = 'login'
        st.rerun()
