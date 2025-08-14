import streamlit as st
import boto3
import base64
import json
import mimetypes

import folders

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
identity_pool_id = 'us-east-2:254bd728-cb37-4779-9cb0-bcb0a4b1c2b1'
region = 'us-east-2'
bucket_name = 'myawsbucket1212398'

identityClient = boto3.client('cognito-identity', region_name=region)
s3Client = None



def authorize_user():
    """Exchange IdToken (from User Pool login) for an IdentityId (Identity Pool)."""
    try:
        response = identityClient.get_id(
            IdentityPoolId=identity_pool_id,
            Logins={f"cognito-idp.{region}.amazonaws.com/{user_pool_id}": st.session_state.IdToken}
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


def getBucketFolder() -> str:
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
            Logins={f"cognito-idp.{region}.amazonaws.com/{user_pool_id}": st.session_state.IdToken}
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

        folders.init_s3(s3Client, bucket_name)

    except Exception as e:
        st.error(f"S3 authentication failed: {e}")



def dashboard_page():
    authenticate_s3()
    if s3Client is None:
        st.stop()

    st.title('Cloud Drive')
    st.write(f"You are logged in as **{st.session_state.username}**.")

    user_root = getBucketFolder()

    if 'current_rel_folder' not in st.session_state:
        st.session_state.current_rel_folder = ''

    st.markdown("### 📁 Folders")

    all_rel_folders = folders.list_all_folders_recursive(user_root)  # e.g., '', 'docs/', 'docs/reports/'

    nav_cols = st.columns([3, 4, 3])
    with nav_cols[0]:
        st.caption("Current folder")
        rel_folder = st.selectbox(
            " ",
            options=all_rel_folders,
            index=all_rel_folders.index(st.session_state.current_rel_folder) if st.session_state.current_rel_folder in all_rel_folders else 0,
            label_visibility="collapsed",
        )
        st.session_state.current_rel_folder = rel_folder

    with nav_cols[1]:
        st.caption("Create a new folder (nested allowed)")
        new_folder_input = st.text_input("e.g., projects or projects/2025/aug", label_visibility="collapsed")

    with nav_cols[2]:
        st.caption(" ")
        if st.button("Create Folder", type="primary", use_container_width=True):
            target_prefix = f"{user_root}{st.session_state.current_rel_folder}"
            if folders.create_folder(target_prefix, new_folder_input):
                st.success(f"Created folder: {new_folder_input}")
                st.rerun()

    st.divider()

    current_abs_prefix = f"{user_root}{st.session_state.current_rel_folder}"
    uploaded_file = st.file_uploader("Upload a file to the current folder", type=None)
    if uploaded_file is not None:
        try:
            content_type, _ = mimetypes.guess_type(uploaded_file.name)
            extra_args = {'ContentType': content_type} if content_type else {}
            s3Client.upload_fileobj(
                uploaded_file,
                bucket_name,
                current_abs_prefix + uploaded_file.name,
                ExtraArgs=extra_args
            )
            st.success(f"File '{uploaded_file.name}' uploaded to {bucket_name}/{st.session_state.current_rel_folder or ''}")
            st.rerun()
        except Exception as e:
            st.error(f"Upload failed: {e}")

    st.divider()

    folder_names, files = folders.list_user_items(current_abs_prefix)

    if folder_names:
        st.markdown("#### Subfolders")
        cols = st.columns(min(len(folder_names), 4))
        for i, name in enumerate(folder_names):
            with cols[i % len(cols)]:
                if st.button(f"📂 {name.rstrip('/')}", key=f"open_{name}"):
                    st.session_state.current_rel_folder = f"{st.session_state.current_rel_folder}{name}"
                    st.rerun()
    else:
        st.info("No subfolders in this folder yet.")

    st.divider()

    st.markdown("### Files")
    selected_keys = folders.render_file_list(files)

    st.divider()

    st.markdown("### Move files")
    if not selected_keys:
        st.caption("Select one or more files above to enable moving.")

    dest_folder = st.selectbox(
        "Destination folder",
        options=all_rel_folders,
        index=all_rel_folders.index(st.session_state.current_rel_folder) if st.session_state.current_rel_folder in all_rel_folders else 0,
        help="Choose where to move the selected files.",
    )

    move_disabled = len(selected_keys) == 0
    if st.button("Move selected files", type="primary", disabled=move_disabled):
        successes = 0
        for src_key in selected_keys:
            filename = src_key.split('/')[-1]
            dst_key = f"{user_root}{dest_folder}{filename}"
            if folders.change_loc(src_key, dst_key):
                successes += 1
        if successes:
            st.success(f"Moved {successes} file(s) to {dest_folder or '(root)'}")
            st.rerun()
        else:
            st.warning("No files were moved.")

    st.divider()
    if st.button("Refresh list"):
        st.rerun()

    if st.button("Logout"):
        for k in ['logged_in', 'username', 'IdToken', 'IdentityId', 'page', 'current_rel_folder']:
            st.session_state.pop(k, None)
        st.session_state.page = 'login'
        st.rerun()
