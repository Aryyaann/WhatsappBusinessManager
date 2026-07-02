import uuid
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class S3Client:
    # El cliente boto3 se crea una sola vez al instanciar la clase.
    # Usamos las credenciales y región directamente desde settings.
    def __init__(self):
        self._client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self._bucket = settings.s3_bucket_name

    def upload_file(self, file_bytes: bytes, prefix: str, content_type: str) -> str:
        # Genera una clave única para cada archivo: prefix/uuid.ext
        # Así los albaranes de distintos negocios nunca colisionan.
        key = f"{prefix}/{uuid.uuid4()}"
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return key

    def download_file(self, key: str) -> bytes:
        # Descarga el archivo como bytes. El worker Celery lo usará
        # para pasar la imagen a Textract y a Claude.
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        # URL firmada con expiración. El frontend puede mostrar la imagen
        # del albarán sin exponer el bucket directamente.
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )


# Instancia única compartida por todo el proceso — patrón singleton ligero.
s3_client = S3Client()