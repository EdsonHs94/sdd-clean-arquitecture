"""Initialize a private disposable local bucket; never provision production AWS."""

import os
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

endpoint = os.environ["S3_ENDPOINT_URL"]
if urlparse(endpoint).hostname not in {"s3", "127.0.0.1", "localhost"}:
    raise RuntimeError("Bucket initialization is limited to the local S3 service")
bucket = os.environ["S3_BUCKET"]
client = boto3.client(
    "s3",
    region_name="us-east-1",
    endpoint_url=endpoint,
    config=Config(connect_timeout=3, read_timeout=5, retries={"total_max_attempts": 3}),
)
try:
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
            raise
    client.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
finally:
    client.close()
