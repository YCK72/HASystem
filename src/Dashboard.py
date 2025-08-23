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

def home_view(abs_root: str):
    st.markdown("## Home")

    summary = folders.summarize_home(abs_root)
    loose_total = sum(o.get("Size", 0) for o in summary["loose_files"])
    folder_total = sum(v["total_size"] for v in summary["folders"].values())
    used_bytes = loose_total + folder_total
    limit_bytes = folders.USER_STORAGE_LIMIT_BYTES
    remaining_bytes = max(0, limit_bytes - used_bytes)

    top_cols = st.columns(4)
    with top_cols[0]:
        st.metric("Top-level folders", f"{len(summary['folders'])}")
    with top_cols[1]:
        total_loose = len(summary["loose_files"])
        st.metric("Loose files", f"{total_loose}")
    with top_cols[2]:
        st.metric("Storage used", f"{folders.human_size(used_bytes)}")
    with top_cols[3]:
        st.metric("Remaining", f"{folders.human_size(remaining_bytes)} / {folders.human_size(limit_bytes)}")

    st.progress(min(1.0, used_bytes / limit_bytes if limit_bytes else 0.0), text=f"{round(100*used_bytes/limit_bytes,1) if limit_bytes else 0}% used")

    st.divider()

    with st.expander("✨ Quick organize"):
        c1, c2 = st.columns([2, 3])
        with c1:
            if st.button("Create default folders", use_container_width=True):
                created = folders.ensure_default_folders(abs_root)
                st.success(f"Default folders ensured. (Created {created} new)")
                st.rerun()

        with c2:
            st.caption("Bulk-move loose files to a folder")
            all_rel_folders = folders.list_all_folders_recursive(abs_root)
            dest = st.selectbox("Destination folder", options=all_rel_folders, index=0)
            new_folder_name = st.text_input("…or create & move into a new folder (name only)")

            to_move = []
            if summary["loose_files"]:
                for obj in summary["loose_files"]:
                    key = obj["Key"]
                    filename = key.split("/")[-1]
                    with st.columns([8, 2])[0]:
                        if st.checkbox(filename, key=f"lf_{key}"):
                            to_move.append(key)

            move_disabled = len(to_move) == 0 and not new_folder_name.strip()
            if st.button("Move selected", type="primary", disabled=move_disabled):
                if new_folder_name.strip():
                    ok = folders.create_folder(abs_root, new_folder_name)
                    if not ok:
                        st.stop()
                    dest_abs = f"{abs_root}{new_folder_name.strip().strip('/')}/"
                else:
                    dest_abs = f"{abs_root}{dest}"

                payload = to_move or [o["Key"] for o in summary["loose_files"]]
                moved = folders.move_many(payload, dest_abs)
                st.success(f"Moved {moved} file(s) to {dest or new_folder_name or '(root)'}")
                st.rerun()

    st.divider()

    # Folders grid
    st.markdown("### 📁 Top-level folders")
    if summary["folders"]:
        names = sorted(summary["folders"].keys())
        cols = st.columns(3)
        for i, name in enumerate(names):
            stats = summary["folders"][name]
            with cols[i % 3]:
                st.markdown(f"**{name.rstrip('/')}**")
                st.caption(f"{stats['subfolder_count']} subfolders · {stats['file_count']} files · {stats['total_size_h']}")
                if st.button("Open", key=f"open_home_{name}"):
                    st.session_state.current_rel_folder = name
                    st.session_state.home_default_to_browser = True
                    st.rerun()
    else:
        st.info("No folders yet. Create one from **Quick organize** above.")

    st.divider()

    # Loose files list
    st.markdown("### 📄 Loose files (not in any folder)")
    if not summary["loose_files"]:
        st.success("Zero loose files 🎉 Everything is inside folders.")
    else:
        _ = folders.render_file_list(summary["loose_files"], key_prefix="home_")

def browser_view(abs_root: str):
    st.markdown("## 📂 Folder Browser")

    if 'current_rel_folder' not in st.session_state:
        st.session_state.current_rel_folder = ''

    all_rel_folders = folders.list_all_folders_recursive(abs_root)  # e.g., '', 'docs/', 'docs/reports/'

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
            target_prefix = f"{abs_root}{st.session_state.current_rel_folder}"
            if folders.create_folder(target_prefix, new_folder_input):
                st.success(f"Created folder: {new_folder_input}")
                st.rerun()

    st.divider()

    current_abs_prefix = f"{abs_root}{st.session_state.current_rel_folder}"

    remaining_bytes, used_bytes = folders.remaining_user_quota(abs_root)
    st.caption(f"Storage: {folders.human_size(used_bytes)} used / {folders.human_size(folders.USER_STORAGE_LIMIT_BYTES)} total · {folders.human_size(remaining_bytes)} remaining")

    uploaded_file = st.file_uploader("Upload a file to the current folder", type=None)
    if uploaded_file is not None:
        file_size = getattr(uploaded_file, "size", None)
        if file_size is None:
            try:
                file_size = len(uploaded_file.getbuffer())
            except Exception:
                try:
                    # Last resort: seek/tell and rewind
                    pos = uploaded_file.tell()
                    uploaded_file.seek(0, 2)
                    file_size = uploaded_file.tell()
                    uploaded_file.seek(pos)
                except Exception:
                    file_size = 0

        if file_size > remaining_bytes:
            st.error(
                f"Upload blocked: file is {folders.human_size(file_size)}, "
                f"but only {folders.human_size(remaining_bytes)} is left in your 100 MB quota."
            )
        else:
            try:
                content_type, _ = mimetypes.guess_type(uploaded_file.name)
                extra_args = {'ContentType': content_type} if content_type else {}
                try:
                    uploaded_file.seek(0)
                except Exception:
                    pass
                s3Client.upload_fileobj(
                    uploaded_file,
                    bucket_name,
                    current_abs_prefix + uploaded_file.name,
                    ExtraArgs=extra_args
                )
                st.success(
                    f"File '{uploaded_file.name}' uploaded to {bucket_name}/{st.session_state.current_rel_folder or ''}"
                )
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
    selected_keys = folders.render_file_list(files, key_prefix="browse_")

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
            dst_key = f"{abs_root}{dest_folder}{filename}"
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

def dashboard_page():
    authenticate_s3()
    if s3Client is None:
        st.stop()

    st.title('Cloud Drive')
    st.write(f"You are logged in as **{st.session_state.username}**.")

    abs_root = getBucketFolder()

    tab_home, tab_browser = st.tabs(["Home", "Browse"])

    with tab_home:
        home_view(abs_root)

    with tab_browser:
        if st.session_state.get("home_default_to_browser"):
            st.session_state["home_default_to_browser"] = False
        browser_view(abs_root)

    st.divider()
    if st.button("Logout"):
        for k in ['logged_in', 'username', 'IdToken', 'IdentityId', 'page', 'current_rel_folder', 'home_default_to_browser']:
            st.session_state.pop(k, None)
        st.session_state.page = 'login'
        st.rerun()
