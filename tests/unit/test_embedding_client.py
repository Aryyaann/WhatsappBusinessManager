import os
from unittest.mock import MagicMock, patch

# El SDK de OpenAI valida la api_key al construir el cliente (a diferencia
# de Anthropic, que no lo hace hasta la primera llamada real). Seteamos una
# key falsa ANTES del import para que este test no dependa de tener
# OPENAI_API_KEY real configurada en el entorno (ej. en CI).
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

from app.infrastructure.embeddings.openai_client import EmbeddingClient, EMBEDDING_MODEL


def make_fake_response(embeddings: list[list[float]]):
    # Simula la forma del objeto que devuelve openai.embeddings.create:
    # response.data es una lista de objetos con atributo .embedding
    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=vec) for vec in embeddings]
    return fake_response


@patch("app.infrastructure.embeddings.openai_client.OpenAI")
def test_embed_batch_returns_vectors_in_order(mock_openai_cls):
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = make_fake_response([[0.1, 0.2], [0.3, 0.4]])
    mock_openai_cls.return_value = mock_client

    client = EmbeddingClient()
    result = client.embed_batch(["Tinte Rubio", "Mascarilla Keratina"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_client.embeddings.create.assert_called_once_with(
        model=EMBEDDING_MODEL,
        input=["Tinte Rubio", "Mascarilla Keratina"],
    )


@patch("app.infrastructure.embeddings.openai_client.OpenAI")
def test_embed_batch_empty_list_returns_empty_without_calling_api(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    client = EmbeddingClient()
    result = client.embed_batch([])

    assert result == []
    mock_client.embeddings.create.assert_not_called()


@patch("app.infrastructure.embeddings.openai_client.OpenAI")
def test_embed_text_returns_single_vector(mock_openai_cls):
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = make_fake_response([[0.5, 0.6]])
    mock_openai_cls.return_value = mock_client

    client = EmbeddingClient()
    result = client.embed_text("Aceite Argán")

    assert result == [0.5, 0.6]