# folders.py
import streamlit as st
import boto3

user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
identity_pool_id = 'us-east-2:254bd728-cb37-4779-9cb0-bcb0a4b1c2b1'
region = 'us-east-2'
bucket_name = 'myawsbucket1212398'

identityClient = boto3.client('cognito-identity', region_name=region)
s3Client = None

def init_s3(client, bucket=None):
    global s3Client, bucket_name
    s3Client = client
    if bucket:
        bucket_name = bucket

char_lst = ["$", "#", "^", "{", "}", "@", "!"]

def create_folder(prefix: str, name: str) -> bool:
    name = name.strip().strip('/')
    if not name:
        st.error("The folder's name cannot be empty.")
        return False
    elif any(c in name for c in char_lst):   # <-- fixed check
        st.error("The folder's name cannot include special characters.")
        return False
    key = f"{prefix}{name}/"

    try:
        if s3Client is None:
            raise RuntimeError("S3 client not initialized. Call init_s3() first.")
        s3Client.put_object(Bucket=bucket_name, Key=key)
        return True
    except Exception as e:
        st.error(f"Failed to create the folder: {e}")
        return False


def change_loc(src_key: str, dst_key: str) -> bool:
    if src_key == dst_key:
        st.warning("Source and destination of the object are the same. This action will not be processed.")
        return False
    try:
        if s3Client is None:
            raise RuntimeError("S3 client not initialized. Call init_s3() first.")
        s3Client.copy_object(
            Bucket=bucket_name,
            CopySource={'Bucket': bucket_name, 'Key': src_key},
            Key=dst_key
        )
        s3Client.delete_object(Bucket=bucket_name, Key=src_key)
        return True
    except Exception as e:
        st.error(f"Failed to move the object {src_key} -> {dst_key}: {e}")
        return False


def paginate_list_objects(prefix: str, delimiter: str = '/'):
    if s3Client is None:
        raise RuntimeError("S3 client not initialized. Call init_s3() first.")
    continuation_token = None
    while True:
        kwargs = {
            'Bucket': bucket_name,
            'Prefix': prefix,
            'Delimiter': delimiter,
            'MaxKeys': 1000
        }
        if continuation_token:
            kwargs['ContinuationToken'] = continuation_token

        resp = s3Client.list_objects_v2(**kwargs)
        # get() with [] already avoids None issues
        folders = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]
        files = [o for o in resp.get('Contents', []) if o.get('Key') != prefix]

        yield folders, files

        if not resp.get('IsTruncated'):
            break
        continuation_token = resp.get('NextContinuationToken')


def list_user_items(prefix: str):
    all_folders = []
    all_files = []
    for folders, files in paginate_list_objects(prefix):
        all_folders.extend(folders)
        all_files.extend(files)
    folder_names = [f[len(prefix):] for f in all_folders]
    return folder_names, all_files


def list_all_folders_recursive(prefix: str):
    to_visit = [prefix]
    seen = set()
    results = ['']  # root
    while to_visit:
        cur = to_visit.pop()
        if cur in seen:
            continue
        seen.add(cur)
        level_folders, _ = list_user_items(cur)
        for name in level_folders:
            full = f"{cur}{name}"
            results.append(full[len(prefix):])
            to_visit.append(full)
    uniq = ['']
    uniq.extend(sorted(set(results[1:])))
    return uniq


def render_file_list(files):
    if not files:
        st.info("No files found in this folder.")
        return []

    selected = []
    for obj in files:
        key = obj['Key']
        filename = key.split('/')[-1]

        left, mid, right = st.columns([6, 2, 2], vertical_alignment="center")
        with left:
            checked = st.checkbox(filename, key=f"chk_{key}")
            if checked:
                selected.append(key)
        with mid:
            st.caption(f"{obj.get('Size', 0)} bytes")
        with right:
            try:
                if s3Client is None:
                    raise RuntimeError("S3 client not initialized. Call init_s3() first.")
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
    return selected
