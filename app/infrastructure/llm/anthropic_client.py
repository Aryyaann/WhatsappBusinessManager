import anthropic

from app.core.config import settings


class AnthropicClient:
    # Cliente oficial de Anthropic. Se instancia una vez y se reutiliza
    # en todas las llamadas — la librería gestiona el connection pooling.
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = "claude-sonnet-4-6"

    def extract_albaran(self, textract_output: dict, system_prompt: str) -> dict:
        # Llama a Claude con el output de Textract para extraer
        # los datos estructurados del albarán.
        # Devuelve el JSON que Claude genera con las líneas del albarán.
        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Texto del albarán:\n{textract_output['raw_text']}\n\n"
                        f"Tablas detectadas:\n{textract_output['tables']}"
                    ),
                }
            ],
        )
        # El contenido viene como lista de bloques — extraemos el texto.
        return {"content": message.content[0].text, "usage": message.usage.model_dump()}

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> anthropic.types.Message:
        # Llamada con function calling para el flujo conversacional.
        # Claude decide qué tool invocar según el intent del mensaje.
        # Devuelve el objeto Message completo — el caller decide cómo procesarlo.
        return self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )


# Instancia única compartida por todo el proceso.
anthropic_client = AnthropicClient()