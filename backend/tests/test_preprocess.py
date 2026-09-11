import numpy as np
from PIL import Image

from app.services.ocr.preprocess import preprocess_for_ocr


def _noisy_gray_image(w=120, h=60) -> Image.Image:
    rng = np.random.default_rng(0)
    arr = np.full((h, w, 3), 200, dtype=np.uint8)
    arr[20:40, 30:90] = 60  # a dark "text" block
    noise = rng.integers(0, 30, size=arr.shape, dtype=np.uint8)
    return Image.fromarray(np.clip(arr.astype(int) - noise, 0, 255).astype(np.uint8))


def test_output_is_binary_grayscale():
    out = preprocess_for_ocr(_noisy_gray_image())
    assert out.mode == "L"
    values = set(np.unique(np.array(out)).tolist())
    assert values <= {0, 255}


def test_small_images_are_upscaled_for_tesseract():
    out = preprocess_for_ocr(_noisy_gray_image(w=120, h=60))
    assert out.width >= 240 and out.height >= 120


def test_dark_text_stays_dark_on_light_background():
    out = np.array(preprocess_for_ocr(_noisy_gray_image()))
    h, w = out.shape
    centre = out[int(h * 0.5), int(w * 0.5)]
    corner = out[2, 2]
    assert centre == 0 and corner == 255
