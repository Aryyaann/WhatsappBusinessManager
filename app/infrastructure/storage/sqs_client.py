import json
from typing import Optional
import boto3

from app.core.config import settings


class SQSClient:
    # El cliente boto3 se crea una sola vez al instanciar la clase,
    # igual que con S3. Las credenciales vienen de settings.
    def __init__(self):
        self._client = boto3.client(
            "sqs",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self._queue_url = settings.sqs_queue_url

    def send_message(self, payload: dict) -> str:
        # Serializa el payload a JSON y lo encola en SQS.
        # El webhook llamará a esto justo después de recibir una foto.
        # Devuelve el MessageId de SQS por si necesitamos trazabilidad.
        response = self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps(payload),
        )
        return response["MessageId"]

    def receive_messages(self, max_messages: int = 1, wait_seconds: int = 20) -> list[dict]:
        # Long polling: espera hasta 20 segundos antes de devolver vacío.
        # Esto reduce llamadas a la API y el coste de SQS.
        # El worker Celery llamará a esto en bucle para consumir jobs.
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_seconds,
        )
        return response.get("Messages", [])

    def delete_message(self, receipt_handle: str) -> None:
        # Elimina el mensaje de la cola después de procesarlo correctamente.
        # Si no se elimina, SQS lo reencola automáticamente tras el timeout.
        # Después de 3 reintentos fallidos va a la DLQ.
        self._client.delete_message(
            QueueUrl=self._queue_url,
            ReceiptHandle=receipt_handle,
        )


# Instancia única compartida por todo el proceso.
sqs_client = SQSClient()