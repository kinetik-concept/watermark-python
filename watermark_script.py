#!/usr/bin/env python3
"""
This script applies a watermark to all images in a specified directory (including subdirectories)
and saves the watermarked images to a destination directory, maintaining the directory structure.

Usage:
    python watermark_script.py --source_dir /path/to/source --dest_dir /path/to/dest --watermark /path/to/watermark.png --opacity 0.5 --position bottom-right --size 0.2 --log_file script.log --verbose
"""

import os
import sys
import argparse
import logging
from PIL import Image, ImageEnhance, UnidentifiedImageError, ImageOps

# Import Resampling with backward compatibility
try:
    from PIL import Image
    RESAMPLING = Image.Resampling.LANCZOS
except AttributeError:
    # For older Pillow versions
    RESAMPLING = Image.ANTIALIAS

def setup_logging(log_file=None, verbose=False):
    """
    Set up logging configuration.

    Parameters:
        log_file (str): Path to the log file. If None, logs will only be printed to console.
        verbose (bool): If True, set log level to DEBUG. Otherwise, set to INFO.
    """
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    if verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(level=log_level, format=log_format, handlers=handlers)

def adjust_opacity(im, opacity):
    """
    Adjust the opacity of an image.

    Parameters:
        im (PIL.Image): The image to adjust.
        opacity (float): The opacity level (0.0 to 1.0).

    Returns:
        PIL.Image: The image with adjusted opacity.
    """
    try:
        assert 0 <= opacity <= 1, "Opacity must be between 0 and 1."
    except AssertionError as e:
        logging.error(e)
        sys.exit(1)

    if im.mode != 'RGBA':
        im = im.convert('RGBA')
        logging.debug("Converted watermark image to RGBA mode for opacity adjustment.")

    # Split the image into its component bands
    r, g, b, alpha = im.split()
    # Apply opacity to the alpha band
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    # Merge back the bands
    im = Image.merge('RGBA', (r, g, b, alpha))
    logging.debug("Adjusted watermark opacity.")
    return im

def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Apply watermark to images in a directory.')
    parser.add_argument('--source_dir', '-s', required=True, help='Path to the source directory.')
    parser.add_argument('--dest_dir', '-d', required=True, help='Path to the destination directory.')
    parser.add_argument('--watermark', '-w', required=True, help='Path to the watermark image.')
    parser.add_argument('--opacity', '-o', type=float, default=0.5, help='Opacity of the watermark (0 to 1).')
    parser.add_argument('--position', '-p', choices=['top-left', 'top-right', 'center', 'bottom-right', 'bottom-left'], default='bottom-right', help='Position of the watermark.')
    parser.add_argument('--size', '-z', type=float, default=0.2, help='Size of the watermark relative to the image (0 to 1).')
    parser.add_argument('--log_file', '-lf', help='Path to the log file.')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging.')
    return parser.parse_args()

def validate_arguments(args):
    """
    Validate the command-line arguments.

    Parameters:
        args (argparse.Namespace): Parsed arguments.
    """
    if not os.path.isdir(args.source_dir):
        logging.error(f"Source directory '{args.source_dir}' does not exist or is not a directory.")
        sys.exit(1)
    if not os.path.isfile(args.watermark):
        logging.error(f"Watermark image '{args.watermark}' does not exist or is not a file.")
        sys.exit(1)
    if not (0 <= args.opacity <=1):
        logging.error("Opacity must be between 0 and 1.")
        sys.exit(1)
    if not (0 < args.size <=1):
        logging.error("Size must be between 0 and 1.")
        sys.exit(1)
    logging.debug("All arguments validated successfully.")

def load_watermark(watermark_path, opacity):
    """
    Load and adjust the watermark image.

    Parameters:
        watermark_path (str): Path to the watermark image.
        opacity (float): Opacity level for the watermark.

    Returns:
        PIL.Image: The processed watermark image.
    """
    try:
        watermark = Image.open(watermark_path)
        logging.debug(f"Watermark image '{watermark_path}' loaded successfully.")
    except FileNotFoundError:
        logging.error(f"Watermark image '{watermark_path}' not found.")
        sys.exit(1)
    except UnidentifiedImageError:
        logging.error(f"Watermark image '{watermark_path}' is not a valid image file.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error loading watermark image: {e}")
        sys.exit(1)

    # Adjust opacity
    watermark = adjust_opacity(watermark, opacity)
    return watermark

def get_watermark_position(position, image_size, watermark_size):
    """
    Calculate the position where the watermark should be placed.

    Parameters:
        position (str): Position keyword.
        image_size (tuple): (width, height) of the original image.
        watermark_size (tuple): (width, height) of the watermark.

    Returns:
        tuple: (x, y) coordinates for the watermark placement.
    """
    im_width, im_height = image_size
    wm_width, wm_height = watermark_size

    margin = 10  # pixels

    if position == 'top-left':
        return (margin, margin)
    elif position == 'top-right':
        return (im_width - wm_width - margin, margin)
    elif position == 'bottom-left':
        return (margin, im_height - wm_height - margin)
    elif position == 'bottom-right':
        return (im_width - wm_width - margin, im_height - wm_height - margin)
    elif position == 'center':
        return ((im_width - wm_width) // 2, (im_height - wm_height) // 2)
    else:
        logging.warning(f"Unknown position '{position}'. Defaulting to bottom-right.")
        return (im_width - wm_width - margin, im_height - wm_height - margin)

def process_image(image_path, watermark, args):
    """
    Apply the watermark to a single image and save it to the destination directory.

    Parameters:
        image_path (str): Path to the original image.
        watermark (PIL.Image): The watermark image.
        args (argparse.Namespace): Parsed command-line arguments.
    """
    try:
        with Image.open(image_path) as im:
            logging.debug(f"Opened image '{image_path}'.")
            original_mode = im.mode
            original_format = im.format

            # Handle EXIF orientation
            im = ImageOps.exif_transpose(im)
            logging.debug(f"Applied EXIF orientation to image '{image_path}'.")

            im_width, im_height = im.size

            # Calculate new size for the watermark
            wm_ratio = args.size
            wm_width = int(im_width * wm_ratio)
            if wm_width == 0:
                logging.warning(f"Calculated watermark width is 0 for image '{image_path}'. Skipping.")
                return
            # Maintain aspect ratio of the watermark
            w_percent = (wm_width / float(watermark.size[0]))
            wm_height = int((float(watermark.size[1]) * float(w_percent)))
            wm_resized = watermark.resize((wm_width, wm_height), RESAMPLING)
            logging.debug(f"Resized watermark to ({wm_width}, {wm_height}).")

            # Determine position
            position = get_watermark_position(args.position, im.size, wm_resized.size)
            logging.debug(f"Watermark position for image '{image_path}': {position}.")

            # Ensure image is in RGBA mode
            if im.mode != 'RGBA':
                im = im.convert('RGBA')
                logging.debug(f"Converted image '{image_path}' to RGBA mode.")

            # Create a transparent layer the size of the image and paste the watermark into it
            layer = Image.new('RGBA', im.size, (0,0,0,0))
            layer.paste(wm_resized, position)
            logging.debug("Pasted resized watermark onto transparent layer.")

            # Composite the watermark with the image
            watermarked = Image.alpha_composite(im, layer)
            logging.debug("Composited watermark with the original image.")

            # Convert back to original mode if needed
            # Handle formats that do not support alpha channels
            non_alpha_formats = ['JPEG', 'JPG', 'BMP', 'WEBP']
            if original_format.upper() in non_alpha_formats:
                watermarked = watermarked.convert('RGB')
                logging.debug(f"Converted watermarked image to 'RGB' mode for format '{original_format}'.")
            elif original_mode != 'RGBA':
                watermarked = watermarked.convert(original_mode)
                logging.debug(f"Converted watermarked image back to original mode '{original_mode}'.")

            # Construct the output path, maintaining the directory structure
            relative_path = os.path.relpath(os.path.dirname(image_path), args.source_dir)
            dest_path = os.path.join(args.dest_dir, relative_path)
            os.makedirs(dest_path, exist_ok=True)
            dest_image_path = os.path.join(dest_path, os.path.basename(image_path))
            logging.debug(f"Destination path for watermarked image: '{dest_image_path}'.")

            # Save the watermarked image
            watermarked.save(dest_image_path, format=original_format)
            logging.info(f"Saved watermarked image to: {dest_image_path}")

    except UnidentifiedImageError:
        logging.error(f"File '{image_path}' is not a valid image or is corrupted.")
    except PermissionError:
        logging.error(f"Permission denied when processing '{image_path}'.")
    except Exception as e:
        logging.error(f"Unexpected error processing image '{image_path}': {e}")

def main():
    # Parse command line arguments
    args = parse_arguments()

    # Set up logging
    setup_logging(args.log_file, args.verbose)
    logging.debug("Logging is set up.")

    # Validate arguments
    validate_arguments(args)

    # Load and process watermark
    watermark = load_watermark(args.watermark, args.opacity)

    # Supported image extensions
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')

    # Walk through the source directory
    logging.info(f"Starting processing images from '{args.source_dir}' to '{args.dest_dir}'.")
    for root, dirs, files in os.walk(args.source_dir):
        for file in files:
            if file.lower().endswith(IMAGE_EXTENSIONS):
                image_path = os.path.join(root, file)
                logging.debug(f"Found image: '{image_path}'.")
                process_image(image_path, watermark, args)
            else:
                logging.debug(f"Skipped non-image file: '{os.path.join(root, file)}'.")

    logging.info("Watermarking process completed.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("Script interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}")
        sys.exit(1)


#python watermark_script.py --source_dir ~/01-no-watermark/ \
#                           --dest_dir ~/02-watermark/ \
#                           --watermark ~/Downloads/missed-mile-markers-logo.jpg \
#                           --opacity 0.5 \
#                           --position bottom-right \
#                           --size 0.2