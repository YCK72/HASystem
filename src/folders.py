# folders.py
import streamlit as st
import boto3
import hashlib
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# (Keep your existing IDs if you need them elsewhere)
user_pool_id = 'us-east-2_Hp4SSNxIw'
client_id = '6q7gaomdohqejt5ckisjioegph'
identity_pool_id = 'us-east-2:254bd728-cb37-4779-9cb0-bcb0a4b1c2b1'
region = 'us-east-2'
bucket_name = 'myawsbucket1212398'

USER_STORAGE_LIMIT_BYTES = 100 * 1024 * 1024  # 104_857_600 bytes

identityClient = boto3.client('cognito-identity', region_name=region)
s3Client = None

def init_s3(client, bucket=None):
    global s3Client, bucket_name
    s3Client = client
    if bucket:
        bucket_name = bucket

char_lst = ["$", "#", "^", "{", "}", "@", "!"]

def _require_s3():
    if s3Client is None:
        raise RuntimeError("S3 client not initialized. Call init_s3() first.")

def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    if i == 0:
        return f"{int(f)} {units[i]}"
    return f"{f:.1f} {units[i]}"

def _sid(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]

def user_storage_usage(abs_root_prefix: str) -> int:
    _require_s3()
    total = 0
    token = None
    while True:
        kwargs = {'Bucket': bucket_name, 'Prefix': abs_root_prefix, 'MaxKeys': 1000}
        if token:
            kwargs['ContinuationToken'] = token
        resp = s3Client.list_objects_v2(**kwargs)
        for obj in resp.get('Contents', []):
            if obj.get('Key') == abs_root_prefix:
                continue  # skip the folder marker
            total += obj.get('Size', 0)
        if not resp.get('IsTruncated'):
            break
        token = resp.get('NextContinuationToken')
    return total

def remaining_user_quota(abs_root_prefix: str) -> Tuple[int, int]:
    used = user_storage_usage(abs_root_prefix)
    remaining = max(0, USER_STORAGE_LIMIT_BYTES - used)
    return remaining, used

def create_folder(prefix: str, name: str) -> bool:
    name = name.strip().strip('/')
    if not name:
        st.error("The folder's name cannot be empty.")
        return False
    elif any(c in name for c in char_lst):
        st.error("The folder's name cannot include special characters.")
        return False
    key = f"{prefix}{name}/"
    try:
        _require_s3()
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
        _require_s3()
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

def move_many(src_keys: List[str], dst_abs_prefix: str) -> int:
    successes = 0
    for src in src_keys:
        fn = src.split('/')[-1]
        dst_key = f"{dst_abs_prefix}{fn}"
        if change_loc(src, dst_key):
            successes += 1
    return successes

def paginate_list_objects(prefix: str, delimiter: str = '/'):
    _require_s3()
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
        folders = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]
        files = [o for o in resp.get('Contents', []) if o.get('Key') != prefix]

        yield folders, files

        if not resp.get('IsTruncated'):
            break
        continuation_token = resp.get('NextContinuationToken')

def list_user_items(prefix: str):
    all_folders = []
    all_files = []
    for folders_page, files_page in paginate_list_objects(prefix):
        all_folders.extend(folders_page)
        all_files.extend(files_page)
    folder_names = [f[len(prefix):] for f in all_folders]
    return folder_names, all_files

def list_all_folders_recursive(prefix: str):
    to_visit = [prefix]
    seen: Set[str] = set()
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

DEFAULT_FOLDERS = ["Documents", "Pictures", "Videos", "Music", "Archives", "Code", "Misc"]

def _folder_exists(abs_root_prefix: str, name: str) -> bool:
    _require_s3()
    key = f"{abs_root_prefix}{name.strip().strip('/')}/"
    resp = s3Client.list_objects_v2(Bucket=bucket_name, Prefix=key, MaxKeys=1)
    return bool(resp.get("Contents"))

def ensure_default_folders(abs_root_prefix: str, names: List[str] = None) -> int:
    names = names or DEFAULT_FOLDERS
    created = 0
    for n in names:
        if not _folder_exists(abs_root_prefix, n):
            if create_folder(abs_root_prefix, n):
                created += 1
    return created

def summarize_home(abs_root_prefix: str) -> Dict:
    _require_s3()

    summary = {
        "folders": {},
        "loose_files": []
    }

    continuation_token = None
    top_level_subfolders: Dict[str, Set[str]] = defaultdict(set)
    top_level_file_counts: Dict[str, int] = defaultdict(int)
    top_level_total_size: Dict[str, int] = defaultdict(int)

    while True:
        kwargs = {
            'Bucket': bucket_name,
            'Prefix': abs_root_prefix,
            'MaxKeys': 1000
        }
        if continuation_token:
            kwargs['ContinuationToken'] = continuation_token

        resp = s3Client.list_objects_v2(**kwargs)
        contents = resp.get('Contents', [])
        for obj in contents:
            key = obj['Key']
            if key == abs_root_prefix:
                continue

            rel = key[len(abs_root_prefix):]  # path relative to user root

            if '/' not in rel:
                # Loose file at root
                summary["loose_files"].append(obj)
                continue

            top, rest = rel.split('/', 1)
            top = top + '/'
            if not rel.endswith('/'):
                top_level_file_counts[top] += 1
                top_level_total_size[top] += obj.get('Size', 0)

            sub1 = rest.split('/', 1)[0] + '/'
            top_level_subfolders[top].add(sub1)

        if not resp.get('IsTruncated'):
            break
        continuation_token = resp.get('NextContinuationToken')

    for top in sorted(set(top_level_file_counts.keys()) | set(top_level_subfolders.keys())):
        summary["folders"][top] = {
            "file_count": top_level_file_counts.get(top, 0),
            "subfolder_count": len(top_level_subfolders.get(top, set())),
            "total_size": top_level_total_size.get(top, 0),
            "total_size_h": human_size(top_level_total_size.get(top, 0)),
        }

    summary["loose_files"].sort(key=lambda x: x.get("LastModified"), reverse=True)

    return summary

def render_file_list(files, key_prefix: str = ""):
    if not files:
        st.info("No files found in this folder.")
        return []

    selected = []
    for obj in files:
        key = obj['Key']
        filename = key.split('/')[-1]
        size = human_size(obj.get('Size', 0))
        sid = _sid(key)

        left, mid, right = st.columns([6, 2, 2], vertical_alignment="center")
        with left:
            checked = st.checkbox(filename, key=f"{key_prefix}chk_{sid}")
            if checked:
                selected.append(key)
        with mid:
            st.caption(size)
        with right:
            try:
                _require_s3()
                obj_resp = s3Client.get_object(Bucket=bucket_name, Key=key)
                file_bytes = obj_resp['Body'].read()
                st.download_button(
                    label="Download",
                    data=file_bytes,
                    file_name=filename,
                    mime="application/octet-stream",
                    key=f"{key_prefix}dl_{sid}"
                )
            except Exception as e:
                st.error(f"Download failed for {filename}: {e}")
    return selected
