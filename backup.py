import os
import subprocess
import boto3
from datetime import datetime

def backup_postgres_to_s3():
    # 1. Load Configuration
    db_url = os.environ.get('DATABASE_URL')
    s3_bucket = os.environ.get('S3_BUCKET_NAME')
    aws_id = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

    if not all([db_url, s3_bucket, aws_id, aws_key]):
        print("Error: Missing required environment variables.")
        print("Ensure DATABASE_URL, S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY are set.")
        return

    # 2. Generate Unique Filename
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"backup_{timestamp}.sql"

    print(f"Starting database backup: {filename}")

    # 3. Create Dump (requires pg_dump to be installed)
    try:
        # pg_dump can accept the connection URI directly
        cmd = f"pg_dump {db_url} -f {filename}"
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running pg_dump: {e}")
        return
    except FileNotFoundError:
        print("Error: pg_dump command not found. Please install postgresql-client tools.")
        return

    # 4. Upload to S3
    try:
        print(f"Uploading {filename} to S3 bucket: {s3_bucket}...")
        s3 = boto3.client('s3', aws_access_key_id=aws_id, aws_secret_access_key=aws_key)
        # Upload to a 'backups/' folder in your bucket
        s3.upload_file(filename, s3_bucket, f"backups/{filename}")
        print("Upload successful!")
    except Exception as e:
        print(f"Error uploading to S3: {e}")
    finally:
        # 5. Cleanup local file
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == '__main__':
    backup_postgres_to_s3()