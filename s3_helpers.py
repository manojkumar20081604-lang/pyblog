import boto3
import os
from botocore.exceptions import NoCredentialsError
from werkzeug.utils import secure_filename
from datetime import datetime

def _get_s3_client():
    """Lazy-initialize S3 client so missing AWS keys don't crash on import."""
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
    )

def upload_file_to_s3(file, acl="public-read"):
    """
    Uploads a file to an S3 bucket.
    Returns {"filename": filename} on success or {"error": "..."} on failure.
    """
    bucket = os.environ.get('S3_BUCKET_NAME')
    if not bucket:
        return {"error": "S3_BUCKET_NAME is not configured."}

    fname = secure_filename(file.filename)
    filename = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + fname

    try:
        s3 = _get_s3_client()
        s3.upload_fileobj(
            file,
            bucket,
            filename,
            ExtraArgs={
                "ACL": acl,
                "ContentType": file.content_type
            }
        )
    except FileNotFoundError:
        return {"error": "File not found."}
    except NoCredentialsError:
        return {"error": "AWS credentials not available."}
    except Exception as e:
        return {"error": str(e)}

    return {"filename": filename}