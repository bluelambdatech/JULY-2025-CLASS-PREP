# s3_backup_tool/__init__.py
# (Empty or used for package-level config)


# s3_backup_tool/config.py
import yaml

def load_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


# s3_backup_tool/logging_setup.py
import os
import logging

def setup_logging(log_file):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


# s3_backup_tool/cache.py
import os
import json

CACHE_FILE = 'file_cache.json'

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


# s3_backup_tool/utils.py
import hashlib
import zipfile
from io import BytesIO
import os

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def compress_file(local_path):
    memory_zip = BytesIO()
    with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(local_path, arcname=os.path.basename(local_path))
    memory_zip.seek(0)
    return memory_zip

def should_upload(file, filters):
    if not filters:
        return True
    ext = os.path.splitext(file)[1].lower()
    return ext in filters


# s3_backup_tool/uploader.py
import logging
from .utils import calculate_md5, compress_file

def upload_compressed_file(s3_client, bucket_name, s3_key, file_data, metadata):
    s3_client.upload_fileobj(file_data, bucket_name, s3_key, ExtraArgs={'Metadata': metadata})

def upload_file_if_changed(s3_client, config, file_path, s3_key, file_cache):
    new_hash = calculate_md5(file_path)
    if file_path in file_cache and file_cache[file_path] == new_hash:
        logging.info(f"Skipping {file_path} (unchanged)")
        return False

    try:
        if config.get("compress_files", False):
            compressed = compress_file(file_path)
            s3_key += ".zip"
            upload_compressed_file(s3_client, config["bucket_name"], s3_key, compressed, {
                "original_filename": os.path.basename(file_path),
                "compressed": "true"
            })
        else:
            s3_client.upload_file(file_path, config["bucket_name"], s3_key)

        logging.info(f"Uploaded {file_path} -> s3://{config['bucket_name']}/{s3_key}")
        file_cache[file_path] = new_hash
        return True
    except Exception as e:
        logging.error(f"Failed to upload {file_path}: {e}")
        return False


# s3_backup_tool/notify.py
import boto3

def notify_sns(topic_arn, message, profile='default'):
    sns = boto3.Session(profile_name=profile).client("sns")
    sns.publish(TopicArn=topic_arn, Subject="S3 Backup Complete", Message=message)


# cli.py
import os
import click
import boto3
import logging
from s3_backup_tool.config import load_config
from s3_backup_tool.logging_setup import setup_logging
from s3_backup_tool.cache import load_cache, save_cache
from s3_backup_tool.utils import should_upload
from s3_backup_tool.uploader import upload_file_if_changed
from s3_backup_tool.notify import notify_sns

@click.command()
@click.option('--config', default='config.yaml', help='Path to config file (YAML)')
@click.option('--dry-run', is_flag=True, help='Simulate uploads without actually uploading')
def backup(config, dry_run):
    config = load_config(config)
    setup_logging(config.get("log_file", "logs/backup.log"))
    s3 = boto3.Session(profile_name=config.get("aws_profile", "default")).client("s3")

    folder = config["upload_dir"]
    bucket = config["bucket_name"]
    filters = config.get("file_filters", [])
    file_cache = load_cache()
    uploaded_files = []

    logging.info(f"Starting backup from '{folder}' to S3 bucket '{bucket}'")
    for root, _, files in os.walk(folder):
        for file in files:
            if not should_upload(file, filters):
                continue

            local_path = os.path.join(root, file)
            s3_key = os.path.relpath(local_path, folder)

            if dry_run:
                logging.info(f"[DRY RUN] Would upload {local_path} to s3://{bucket}/{s3_key}")
            else:
                success = upload_file_if_changed(s3, config, local_path, s3_key, file_cache)
                if success:
                    uploaded_files.append(local_path)

    save_cache(file_cache)

    # SNS notification
    if "sns_topic_arn" in config and not dry_run:
        try:
            notify_sns(config["sns_topic_arn"], f"Backup complete. Uploaded {len(uploaded_files)} file(s).", profile=config.get("aws_profile", "default"))
            logging.info("SNS notification sent.")
        except Exception as e:
            logging.warning(f"Failed to send SNS notification: {e}")

    logging.info("Backup process finished.")

if __name__ == "__main__":
    backup()
