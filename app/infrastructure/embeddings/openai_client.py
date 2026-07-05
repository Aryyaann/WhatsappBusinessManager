from openai import OpenAI

from app.core.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingClient:
    # Cliente oficial de OpenAI, mismo patrón que anthropic_client:
    # se instancia una vez y se reutiliza en todo el proceso.
    def __init__(self):
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = EMBEDDING_MODEL

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Genera embeddings para una lista de textos en una sola llamada.
        # OpenAI devuelve los resultados en el mismo orden que el input,
        # así que no hace falta reordenar nada.
        # Útil para generar de golpe los embeddings de un catálogo entero.
        if not texts:
            return []

        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def embed_text(self, text: str) -> list[float]:
        # Atajo para el caso de un solo texto (ej. producto nuevo suelto).
        # Reutiliza embed_batch para no duplicar lógica.
        return self.embed_batch([text])[0]


# Instancia única compartida por todo el proceso.
embedding_client = EmbeddingClient()