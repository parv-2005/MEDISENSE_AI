"""Image preprocessing before Tesseract (Enhance, Denoise, Threshold).

Tesseract's accuracy on lab reports improves markedly when it receives a
high-resolution, high-contrast, binarised grayscale image with little noise.
"""
import cv2
import numpy as np
from PIL import Image

MIN_WIDTH = 1200  # Tesseract likes ~300 DPI; a phone photo of A4 is often smaller.


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Enhance: upscale small images so glyphs are >= ~20px tall.
    scale = max(2.0, MIN_WIDTH / gray.shape[1]) if gray.shape[1] < MIN_WIDTH else 1.0
    if scale > 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Denoise while keeping edges (bilateral) then remove speckle (median).
    gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    gray = cv2.medianBlur(gray, 3)

    # Threshold: Otsu picks the split between ink and paper automatically.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binary, mode="L")
