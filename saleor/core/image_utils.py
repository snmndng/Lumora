"""
Optimized image processing utilities for Vercel deployment.
"""
import io
import os
from typing import Optional, Tuple

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps


def optimize_image_for_upload(
    image_file: InMemoryUploadedFile,
    max_size: Tuple[int, int] = (2048, 2048),
    quality: int = 85,
    format: str = "JPEG"
) -> Optional[ContentFile]:
    """
    Optimize image for upload to reduce memory usage on Vercel.
    
    Args:
        image_file: Uploaded image file
        max_size: Maximum dimensions (width, height)
        quality: JPEG quality (1-100)
        format: Output format (JPEG, PNG, WEBP)
    
    Returns:
        Optimized ContentFile or None if processing fails
    """
    try:
        # Open and process image
        with Image.open(image_file) as img:
            # Convert to RGB if necessary (for JPEG)
            if format == "JPEG" and img.mode in ("RGBA", "P"):
                # Create white background for transparency
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            
            # Auto-orient based on EXIF data
            img = ImageOps.exif_transpose(img)
            
            # Resize if needed
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save to memory buffer
            output = io.BytesIO()
            save_kwargs = {"format": format, "optimize": True}
            
            if format == "JPEG":
                save_kwargs["quality"] = quality
                save_kwargs["progressive"] = True
            elif format == "PNG":
                save_kwargs["compress_level"] = 6
            elif format == "WEBP":
                save_kwargs["quality"] = quality
                save_kwargs["method"] = 6
            
            img.save(output, **save_kwargs)
            output.seek(0)
            
            # Create new filename
            name, ext = os.path.splitext(image_file.name)
            new_name = f"{name}_optimized.{format.lower()}"
            
            return ContentFile(output.getvalue(), name=new_name)
            
    except Exception as e:
        # Log error but don't crash
        print(f"Image optimization failed: {e}")
        return None


def get_image_dimensions(image_file: InMemoryUploadedFile) -> Optional[Tuple[int, int]]:
    """
    Get image dimensions without loading full image into memory.
    """
    try:
        with Image.open(image_file) as img:
            return img.size
    except Exception:
        return None


def estimate_memory_usage(image_file: InMemoryUploadedFile) -> int:
    """
    Estimate memory usage for image processing.
    """
    dimensions = get_image_dimensions(image_file)
    if not dimensions:
        return 0
    
    width, height = dimensions
    # Rough estimate: width * height * 4 bytes (RGBA) * 2 (for processing)
    return width * height * 4 * 2