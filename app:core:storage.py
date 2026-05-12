import boto3
from botocore.client import Config
from typing import Optional
from .config import settings

class StorageService:
    """S3-compatible storage (MinIO for dev, S3 for production)."""
    
    def __init__(self):
        self.client: Optional[boto3.client] = None
        self.bucket = settings.S3_BUCKET
    
    async def init(self):
        """Initialize S3 client and ensure bucket exists."""
        self.client = boto3.client(
            's3',
            endpoint_url=f"http://{settings.S3_ENDPOINT}",
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            use_ssl=settings.S3_USE_SSL,
            config=Config(signature_version='s3v4')
        )
        
        # Create bucket if it doesn't exist
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except:
            self.client.create_bucket(Bucket=self.bucket)
    
    async def upload_file(self, bucket: str, key: str, content: bytes, content_type: str) -> str:
        """Upload file to bucket and return S3 URI."""
        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type
        )
        return f"s3://{bucket}/{key}"
    
    async def download_file(self, bucket: str, key: str) -> bytes:
        """Download file from bucket."""
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read()

storage = StorageService()