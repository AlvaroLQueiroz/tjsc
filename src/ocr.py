import asyncio
import logging
from pathlib import Path
from typing import Any, Coroutine
import easyocr
from pdf2image import convert_from_path
import itertools

from src.constants import CONVERTED_PATH

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def convert_pdf_to_images(pdf_path: Path) -> Path:
    logging.info(f"Converting PDF to images: {pdf_path}")
    folder_path = CONVERTED_PATH / pdf_path.parent.name / pdf_path.stem
    folder_path.mkdir(parents=True, exist_ok=True)
    convert_from_path(
        pdf_path,
        thread_count=4,
        fmt="jpeg",
        output_folder=folder_path,
        output_file=pdf_path.stem,
    )
    return folder_path


async def extract_text_from_image(image_path: Path) -> list[str]:
    logging.info(f"Extracting text from image: {image_path}")
    reader = easyocr.Reader(["pt"])
    raw = reader.readtext(image_path.as_posix(), output_format="dict")
    result = [block["text"] for block in raw]
    return result


async def extract_text_from_images(folder_path: Path) -> list[list[str]]:
    images_path: list[Coroutine[Any, Path, list[str]]] = []
    for img_path in folder_path.glob("*.jpg"):
        images_path.append(extract_text_from_image(img_path))
    return await asyncio.gather(*images_path)


async def extract_text_from_pdf(pdf_path: Path) -> str:
    img_path = convert_pdf_to_images(pdf_path)
    files_text = await extract_text_from_images(img_path)
    logging.info(f"Extracted text from PDF: {pdf_path} {len(files_text)} pages")
    return "\n".join(itertools.chain.from_iterable(files_text))


if __name__ == "__main__":
    pdf_path = Path("ata.pdf")
    bla = asyncio.run(extract_text_from_pdf(pdf_path))
    print(bla)
