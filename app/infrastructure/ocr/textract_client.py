import json
import boto3

from app.core.config import settings


class TextractClient:
    # Cliente boto3 para Textract, igual que S3 y SQS.
    # Usamos detect_document_text para texto plano y
    # analyze_document para tablas estructuradas.
    def __init__(self):
        self._client = boto3.client(
            "textract",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def extract_text_and_tables(self, image_bytes: bytes) -> dict:
        # Llama a Textract con los bytes de la imagen.
        # FeatureTypes=["TABLES"] activa la detección de tablas además del texto.
        # Los albaranes suelen tener sus líneas en formato tabla.
        response = self._client.analyze_document(
            Document={"Bytes": image_bytes},
            FeatureTypes=["TABLES"],
        )

        # Separamos los bloques por tipo para facilitar el procesamiento.
        # Textract devuelve todo mezclado — líneas, palabras, celdas, tablas.
        blocks = response.get("Blocks", [])
        raw_text = self._extract_raw_text(blocks)
        tables = self._extract_tables(blocks)

        return {
            "raw_text": raw_text,
            "tables": tables,
            "block_count": len(blocks),
        }

    def _extract_raw_text(self, blocks: list) -> str:
        # Concatena todas las líneas detectadas en orden.
        # Esto da el texto completo del albarán como string limpio.
        lines = [
            block["Text"]
            for block in blocks
            if block["BlockType"] == "LINE"
        ]
        return "\n".join(lines)

    def _extract_tables(self, blocks: list) -> list[list[str]]:
        # Reconstruye las tablas a partir de los bloques CELL.
        # Textract identifica cada celda con su fila y columna.
        # Resultado: lista de tablas, cada tabla es una lista de filas.
        block_map = {block["Id"]: block for block in blocks}
        tables = []

        for block in blocks:
            if block["BlockType"] != "TABLE":
                continue

            # Recogemos todas las celdas de esta tabla.
            cells: dict[tuple, str] = {}
            for rel in block.get("Relationships", []):
                if rel["Type"] != "CHILD":
                    continue
                for cell_id in rel["Ids"]:
                    cell = block_map.get(cell_id, {})
                    if cell.get("BlockType") != "CELL":
                        continue
                    row = cell["RowIndex"]
                    col = cell["ColumnIndex"]
                    # Texto de la celda: concatenamos sus palabras hijo.
                    words = []
                    for word_rel in cell.get("Relationships", []):
                        if word_rel["Type"] != "CHILD":
                            continue
                        for word_id in word_rel["Ids"]:
                            word_block = block_map.get(word_id, {})
                            if word_block.get("BlockType") == "WORD":
                                words.append(word_block["Text"])
                    cells[(row, col)] = " ".join(words)

            if not cells:
                continue

            # Reconstruimos la tabla como lista de listas.
            max_row = max(r for r, c in cells)
            max_col = max(c for r, c in cells)
            table = [
                [cells.get((r, c), "") for c in range(1, max_col + 1)]
                for r in range(1, max_row + 1)
            ]
            tables.append(table)

        return tables


# Instancia única compartida por todo el proceso.
textract_client = TextractClient()