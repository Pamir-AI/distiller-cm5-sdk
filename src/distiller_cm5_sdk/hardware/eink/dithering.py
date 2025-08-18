#!/usr/bin/env python3
"""Dithering algorithms for e-ink displays."""

from dataclasses import dataclass

import numpy as np
from PIL import Image


class DitheringConstants:
    """Dithering algorithm constants."""

    # Grayscale conversion weights
    R_WEIGHT = 77
    G_WEIGHT = 151
    B_WEIGHT = 30
    THRESHOLD = 127
    # Bit shift divisors
    SHIFT_8 = 8
    SHIFT_4 = 4
    SHIFT_5 = 5
    SHIFT_2 = 2


@dataclass
class ErrorKernel:
    """Error diffusion kernel definition."""

    offsets: list[tuple[int, int]]  # (y_offset, x_offset)
    weights: list[int]  # Weight for each offset
    divisor_shift: int  # Bit shift for division


class BaseDitherer:
    """Base class for error diffusion dithering."""

    def __init__(self, kernel: ErrorKernel):
        self.kernel = kernel

    def apply(self, gray_data: np.ndarray) -> np.ndarray:
        """Apply dithering with error diffusion."""
        height, width = gray_data.shape
        buffer = gray_data.astype(np.int16)

        for y in range(height):
            for x in range(width):
                old_pixel = buffer[y, x]
                new_pixel = 255 if old_pixel >= DitheringConstants.THRESHOLD else 0
                buffer[y, x] = new_pixel

                q_err = old_pixel - new_pixel

                # Distribute error according to kernel
                for (dy, dx), weight in zip(self.kernel.offsets, self.kernel.weights, strict=False):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        buffer[ny, nx] += (q_err * weight) >> self.kernel.divisor_shift

        return buffer.astype(np.uint8)


# Define standard kernels
FLOYD_STEINBERG_KERNEL = ErrorKernel(
    offsets=[(0, 1), (1, -1), (1, 0), (1, 1)],
    weights=[7, 3, 5, 1],
    divisor_shift=DitheringConstants.SHIFT_4,
)

SIERRA_LITE_KERNEL = ErrorKernel(
    offsets=[(0, 1), (1, -1), (1, 0)], weights=[2, 1, 1], divisor_shift=DitheringConstants.SHIFT_2
)


def rgb_to_grayscale_fast(rgb_data: np.ndarray) -> np.ndarray:
    """Fast RGB to grayscale conversion."""
    if rgb_data.dtype != np.uint8:
        rgb_data = rgb_data.astype(np.uint8)

    gray = (
        (rgb_data[..., 0].astype(np.uint32) * DitheringConstants.R_WEIGHT)
        + (rgb_data[..., 1].astype(np.uint32) * DitheringConstants.G_WEIGHT)
        + (rgb_data[..., 2].astype(np.uint32) * DitheringConstants.B_WEIGHT)
    ) >> DitheringConstants.SHIFT_8

    return gray.astype(np.uint8)


def rgb565_to_grayscale(rgb565_data: np.ndarray) -> np.ndarray:
    """Convert RGB565 to grayscale."""
    r = ((rgb565_data & 0xF800) >> 11) << 3
    g = ((rgb565_data & 0x7E0) >> 5) << 2
    b = (rgb565_data & 0x1F) << 3

    gray = (
        (r.astype(np.uint32) * DitheringConstants.R_WEIGHT)
        + (g.astype(np.uint32) * DitheringConstants.G_WEIGHT)
        + (b.astype(np.uint32) * DitheringConstants.B_WEIGHT)
    ) >> DitheringConstants.SHIFT_8

    return gray.astype(np.uint8)


def apply_threshold_dithering(
    gray_data: np.ndarray, threshold: int = DitheringConstants.THRESHOLD
) -> np.ndarray:
    """Simple threshold dithering."""
    return np.where(gray_data > threshold, 255, 0).astype(np.uint8)


def apply_floyd_steinberg_dithering(gray_data: np.ndarray) -> np.ndarray:
    """Floyd-Steinberg dithering (7/16, 3/16, 5/16, 1/16)."""
    ditherer = BaseDitherer(FLOYD_STEINBERG_KERNEL)
    return ditherer.apply(gray_data)


def apply_sierra_dithering(gray_data: np.ndarray) -> np.ndarray:
    """Sierra dithering (3-row error diffusion)."""
    height, width = gray_data.shape
    buffer = gray_data.astype(np.int16)

    for y in range(height):
        for x in range(width):
            old_pixel = buffer[y, x]
            new_pixel = 255 if old_pixel >= DitheringConstants.THRESHOLD else 0
            buffer[y, x] = new_pixel

            q_err = old_pixel - new_pixel

            if x + 1 < width:
                buffer[y, x + 1] += (q_err * 5) >> DitheringConstants.SHIFT_5
            if x + 2 < width:
                buffer[y, x + 2] += (q_err * 3) >> DitheringConstants.SHIFT_5

            if y + 1 < height:
                if x > 1:
                    buffer[y + 1, x - 2] += (q_err * 2) >> DitheringConstants.SHIFT_5
                if x > 0:
                    buffer[y + 1, x - 1] += (q_err * 4) >> DitheringConstants.SHIFT_5
                buffer[y + 1, x] += (q_err * 5) >> DitheringConstants.SHIFT_5
                if x + 1 < width:
                    buffer[y + 1, x + 1] += (q_err * 4) >> DitheringConstants.SHIFT_5
                if x + 2 < width:
                    buffer[y + 1, x + 2] += (q_err * 2) >> DitheringConstants.SHIFT_5

            if y + 2 < height:
                if x > 0:
                    buffer[y + 2, x - 1] += (q_err * 2) >> DitheringConstants.SHIFT_5
                buffer[y + 2, x] += (q_err * 3) >> DitheringConstants.SHIFT_5
                if x + 1 < width:
                    buffer[y + 2, x + 1] += (q_err * 2) >> DitheringConstants.SHIFT_5

    return buffer.astype(np.uint8)


def apply_sierra_2row_dithering(gray_data: np.ndarray) -> np.ndarray:
    """Sierra 2-row dithering (faster variant)."""
    height, width = gray_data.shape
    buffer = gray_data.astype(np.int16)

    for y in range(height):
        for x in range(width):
            old_pixel = buffer[y, x]
            new_pixel = 255 if old_pixel >= DitheringConstants.THRESHOLD else 0
            buffer[y, x] = new_pixel

            q_err = old_pixel - new_pixel

            if x + 1 < width:
                buffer[y, x + 1] += (q_err * 4) >> DitheringConstants.SHIFT_4
            if x + 2 < width:
                buffer[y, x + 2] += (q_err * 3) >> DitheringConstants.SHIFT_4

            if y + 1 < height:
                if x > 1:
                    buffer[y + 1, x - 2] += (q_err * 1) >> DitheringConstants.SHIFT_4
                if x > 0:
                    buffer[y + 1, x - 1] += (q_err * 2) >> DitheringConstants.SHIFT_4
                buffer[y + 1, x] += (q_err * 3) >> DitheringConstants.SHIFT_4
                if x + 1 < width:
                    buffer[y + 1, x + 1] += (q_err * 2) >> DitheringConstants.SHIFT_4
                if x + 2 < width:
                    buffer[y + 1, x + 2] += (q_err * 1) >> DitheringConstants.SHIFT_4

    return buffer.astype(np.uint8)


def apply_sierra_lite_dithering(gray_data: np.ndarray) -> np.ndarray:
    """Sierra Lite dithering (minimal error distribution)."""
    ditherer = BaseDitherer(SIERRA_LITE_KERNEL)
    return ditherer.apply(gray_data)


def dither_image(image: Image.Image, method: int) -> np.ndarray:
    """Apply dithering to image."""
    if image.mode != "L":
        if image.mode == "RGB":
            rgb_array = np.array(image)
            gray_array = rgb_to_grayscale_fast(rgb_array)
        else:
            gray_image = image.convert("L")
            gray_array = np.array(gray_image)
    else:
        gray_array = np.array(image)

    # Apply dithering
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
    if method == 5:  # SIMPLE
        return apply_threshold_dithering(gray_array)

    raise ValueError(f"Unknown dithering method: {method}")


def pack_1bit_data(binary_data: np.ndarray) -> bytes:
    """Pack binary data into 1-bit format (MSB-first)."""
    height, width = binary_data.shape
    total_pixels = height * width
    total_bytes = (total_pixels + 7) // 8

    bits = (binary_data > DitheringConstants.THRESHOLD).astype(np.uint8)

    if total_pixels % 8 != 0:
        padding = 8 - (total_pixels % 8)
        bits_flat = bits.flatten()
        bits_flat = np.pad(bits_flat, (0, padding), "constant", constant_values=0)
    else:
        bits_flat = bits.flatten()

    packed = np.zeros(total_bytes, dtype=np.uint8)
    for i in range(0, len(bits_flat), 8):
        byte_val = 0
        for j in range(8):
            if i + j < len(bits_flat) and bits_flat[i + j]:
                byte_val |= 1 << (7 - j)
        packed[i // 8] = byte_val

    return packed.tobytes()
