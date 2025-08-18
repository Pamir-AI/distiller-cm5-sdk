#!/usr/bin/env python3
"""
Native dithering algorithms for e-ink displays.
"""

import numpy as np
from PIL import Image


def rgb_to_grayscale_fast(rgb_data: np.ndarray) -> np.ndarray:
    """
    Fast RGB to grayscale conversion
    Formula: ((r * 77) + (g * 151) + (b * 30)) >> 8

    Args:
        rgb_data: RGB data as numpy array with shape (height, width, 3)

    Returns:
        Grayscale data as numpy array with shape (height, width)
    """
    if rgb_data.dtype != np.uint8:
        rgb_data = rgb_data.astype(np.uint8)

    gray = (
        (rgb_data[..., 0].astype(np.uint32) * 77)
        + (rgb_data[..., 1].astype(np.uint32) * 151)
        + (rgb_data[..., 2].astype(np.uint32) * 30)
    ) >> 8

    return gray.astype(np.uint8)


def rgb565_to_grayscale(rgb565_data: np.ndarray) -> np.ndarray:
    """
    Convert RGB565 data to grayscale

    Args:
        rgb565_data: RGB565 data as numpy array of uint16

    Returns:
        Grayscale data as numpy array of uint8
    """
    # Extract RGB components from RGB565
    r = ((rgb565_data & 0xF800) >> 11) << 3  # 5 bits -> 8 bits
    g = ((rgb565_data & 0x7E0) >> 5) << 2  # 6 bits -> 8 bits
    b = (rgb565_data & 0x1F) << 3  # 5 bits -> 8 bits

    # Apply grayscale formula
    gray = (
        (r.astype(np.uint32) * 77) + (g.astype(np.uint32) * 151) + (b.astype(np.uint32) * 30)
    ) >> 8

    return gray.astype(np.uint8)


def apply_threshold_dithering(gray_data: np.ndarray, threshold: int = 127) -> np.ndarray:
    """
    Apply simple threshold dithering (no error diffusion).

    Args:
        gray_data: Grayscale data as numpy array
        threshold: Threshold value (0-255)

    Returns:
        Binary data (0 or 255)
    """
    return np.where(gray_data > threshold, 255, 0).astype(np.uint8)


def apply_floyd_steinberg_dithering(gray_data: np.ndarray) -> np.ndarray:
    """
    Apply Floyd-Steinberg dithering
    Error distribution: right=7/16, bottom-left=3/16, bottom=5/16, bottom-right=1/16

    Args:
        gray_data: Grayscale input data as numpy array

    Returns:
        Dithered binary data (0 or 255)
    """
    height, width = gray_data.shape

    # Work with signed integers to handle negative errors
    buffer = gray_data.astype(np.int16)

    for y in range(height):
        for x in range(width):
            old_pixel = buffer[y, x]
            new_pixel = 255 if old_pixel >= 127 else 0
            buffer[y, x] = new_pixel

            # Calculate quantization error
            q_err = old_pixel - new_pixel

            # Distribute error using bit shifts for efficiency (matching C code)
            if x + 1 < width:
                buffer[y, x + 1] += (q_err * 7) >> 4  # 7/16

            if y + 1 < height:
                if x > 0:
                    buffer[y + 1, x - 1] += (q_err * 3) >> 4  # 3/16
                buffer[y + 1, x] += (q_err * 5) >> 4  # 5/16
                if x + 1 < width:
                    buffer[y + 1, x + 1] += (q_err * 1) >> 4  # 1/16

    return buffer.astype(np.uint8)


def apply_sierra_dithering(gray_data: np.ndarray) -> np.ndarray:
    """
    Apply Sierra dithering algorithm.
    Error distribution over 3 rows with total divisor of 32.

    Args:
        gray_data: Grayscale input data as numpy array

    Returns:
        Dithered binary data (0 or 255)
    """
    height, width = gray_data.shape
    buffer = gray_data.astype(np.int16)

    for y in range(height):
        for x in range(width):
            old_pixel = buffer[y, x]
            new_pixel = 255 if old_pixel >= 127 else 0
            buffer[y, x] = new_pixel

            q_err = old_pixel - new_pixel

            # Row 0 (current row)
            if x + 1 < width:
                buffer[y, x + 1] += (q_err * 5) >> 5  # 5/32
            if x + 2 < width:
                buffer[y, x + 2] += (q_err * 3) >> 5  # 3/32

            # Row 1 (next row)
            if y + 1 < height:
                if x > 1:
                    buffer[y + 1, x - 2] += (q_err * 2) >> 5  # 2/32
                if x > 0:
                    buffer[y + 1, x - 1] += (q_err * 4) >> 5  # 4/32
                buffer[y + 1, x] += (q_err * 5) >> 5  # 5/32
                if x + 1 < width:
                    buffer[y + 1, x + 1] += (q_err * 4) >> 5  # 4/32
                if x + 2 < width:
                    buffer[y + 1, x + 2] += (q_err * 2) >> 5  # 2/32

            # Row 2 (second next row)
            if y + 2 < height:
                if x > 0:
                    buffer[y + 2, x - 1] += (q_err * 2) >> 5  # 2/32
                buffer[y + 2, x] += (q_err * 3) >> 5  # 3/32
                if x + 1 < width:
                    buffer[y + 2, x + 1] += (q_err * 2) >> 5  # 2/32

    return buffer.astype(np.uint8)


def apply_sierra_2row_dithering(gray_data: np.ndarray) -> np.ndarray:
    """
    Apply Sierra 2-row dithering algorithm (faster than full Sierra).
    Error distribution over 2 rows with total divisor of 16.

    Args:
        gray_data: Grayscale input data as numpy array

    Returns:
        Dithered binary data (0 or 255)
    """
    height, width = gray_data.shape
    buffer = gray_data.astype(np.int16)

    for y in range(height):
        for x in range(width):
            old_pixel = buffer[y, x]
            new_pixel = 255 if old_pixel >= 127 else 0
            buffer[y, x] = new_pixel

            q_err = old_pixel - new_pixel

            # Row 0 (current row)
            if x + 1 < width:
                buffer[y, x + 1] += (q_err * 4) >> 4  # 4/16
            if x + 2 < width:
                buffer[y, x + 2] += (q_err * 3) >> 4  # 3/16

            # Row 1 (next row)
            if y + 1 < height:
                if x > 1:
                    buffer[y + 1, x - 2] += (q_err * 1) >> 4  # 1/16
                if x > 0:
                    buffer[y + 1, x - 1] += (q_err * 2) >> 4  # 2/16
                buffer[y + 1, x] += (q_err * 3) >> 4  # 3/16
                if x + 1 < width:
                    buffer[y + 1, x + 1] += (q_err * 2) >> 4  # 2/16
                if x + 2 < width:
                    buffer[y + 1, x + 2] += (q_err * 1) >> 4  # 1/16

    return buffer.astype(np.uint8)


def apply_sierra_lite_dithering(gray_data: np.ndarray) -> np.ndarray:
    """
    Apply Sierra Lite dithering algorithm (fastest Sierra variant).
    Minimal error distribution with total divisor of 4.

    Args:
        gray_data: Grayscale input data as numpy array

    Returns:
        Dithered binary data (0 or 255)
    """
    height, width = gray_data.shape
    buffer = gray_data.astype(np.int16)

    for y in range(height):
        for x in range(width):
            old_pixel = buffer[y, x]
            new_pixel = 255 if old_pixel >= 127 else 0
            buffer[y, x] = new_pixel

            q_err = old_pixel - new_pixel

            # Very simple error distribution
            if x + 1 < width:
                buffer[y, x + 1] += (q_err * 2) >> 2  # 2/4 = 1/2

            if y + 1 < height:
                if x > 0:
                    buffer[y + 1, x - 1] += (q_err * 1) >> 2  # 1/4
                buffer[y + 1, x] += (q_err * 1) >> 2  # 1/4

    return buffer.astype(np.uint8)


def dither_image(image: Image.Image, method: int) -> np.ndarray:
    """
    Apply dithering to a PIL Image using the specified method.

    Args:
        image: PIL Image (will be converted to grayscale if needed)
        method: Dithering method (DitheringMethod enum value)

    Returns:
        Dithered binary data as numpy array (0 or 255)
    """
    # Convert to grayscale if needed
    if image.mode != "L":
        if image.mode == "RGB":
            # Use our fast conversion for RGB
            rgb_array = np.array(image)
            gray_array = rgb_to_grayscale_fast(rgb_array)
        else:
            # Let PIL handle other formats
            gray_image = image.convert("L")
            gray_array = np.array(gray_image)
    else:
        gray_array = np.array(image)

    # Apply the specified dithering method
    if method == 0:  # NONE
        return apply_threshold_dithering(gray_array)
    if method == 1:  # FLOYD_STEINBERG
        return apply_floyd_steinberg_dithering(gray_array)
    if method == 2:  # SIERRA
        return apply_sierra_dithering(gray_array)
    if method == 3:  # SIERRA_2ROW
        return apply_sierra_2row_dithering(gray_array)
    if method == 4:  # SIERRA_LITE
        return apply_sierra_lite_dithering(gray_array)
    if method == 5:  # SIMPLE (legacy)
        return apply_threshold_dithering(gray_array)

    raise ValueError(f"Unknown dithering method: {method}")


def pack_1bit_data(binary_data: np.ndarray) -> bytes:
    """
    Pack binary data (0/255 values) into 1-bit packed format.
    Uses MSB-first bit ordering

    Args:
        binary_data: Binary image data (0 or 255) as numpy array

    Returns:
        Packed 1-bit data as bytes
    """
    height, width = binary_data.shape
    total_pixels = height * width
    total_bytes = (total_pixels + 7) // 8

    # Convert to binary (0 or 1)
    bits = (binary_data > 127).astype(np.uint8)

    # Pad to multiple of 8 if needed
    if total_pixels % 8 != 0:
        padding = 8 - (total_pixels % 8)
        bits_flat = bits.flatten()
        bits_flat = np.pad(bits_flat, (0, padding), "constant", constant_values=0)
    else:
        bits_flat = bits.flatten()

    # Pack 8 bits into each byte (MSB first)
    packed = np.zeros(total_bytes, dtype=np.uint8)
    for i in range(0, len(bits_flat), 8):
        byte_val = 0
        for j in range(8):
            if i + j < len(bits_flat) and bits_flat[i + j]:
                byte_val |= 1 << (7 - j)  # MSB first
        packed[i // 8] = byte_val

    return packed.tobytes()
