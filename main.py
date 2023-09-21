#!/usr/bin/env python3

import os
import sys
import json
import logging
import shutil

from pathlib import Path

from PIL import Image
from rich.logging import RichHandler

from datetime import datetime, timezone

def transform_grep_pattern(ext):
    pattern = ""
    for x in ext:
        pattern += f"[{x.upper()}{x.lower()}]"
    return pattern


def get_valid_images(folder_path) -> list[Path]:
    IMAGE_PATTERNS_TO_GREP = ["jpg", "jpeg", "png"]
    raw_images = []
    for pattern in IMAGE_PATTERNS_TO_GREP:
        raw_images.extend(fetch_files(folder_path, f"**/*.{transform_grep_pattern(pattern)}"))

    valid_images = [img for img in raw_images if not ".compressed" in str(img)]
    [os.makedirs(f"{image.parent}.compressed", exist_ok=True) for image in valid_images]
    return valid_images


def fetch_files(path, expr):
    return list(Path(path).glob(expr))


def compress_image(image_path):
    img = Image.open(image_path)
    exif = get_exif_of_image(image_path)
    img.save(get_dest_path(image_path), optimize=True, exif=exif)


def get_dest_path(src_file_path):
    src = Path(src_file_path)
    dst = f"{src.parent}.compressed/{src.name}"
    return dst


def get_file_size(file):
    return os.path.getsize(file)

def get_shrink_stats(src_filepath, dst_filepath):
    pre_size = get_file_size(src_filepath)
    pos_size = get_file_size(dst_filepath)
    percentage = (pre_size - pos_size) * 100 / pre_size
    return percentage


def configure_logging():
    FORMAT = "%(message)s"
    logging.basicConfig(level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

def get_exif_of_image(src_im_path):
    global NO_EXIF
    img = Image.open(src_im_path)

    # from src image
    exif = img.getexif()
    
    if exif.get(306):
        return exif

    # from json
    json_exif = get_exif_from_json(src_im_path)
    if json_exif.get(306):
        exif[306] = json_exif[306]
        return exif

    # from parsing SIGNAL_IMG_DD_MM_YYYY

    # from parsing IMG_DD_MM_YYYY

    logging.error(f"skipping exif {src_im_path}")
    NO_EXIF += 1
    return exif

def get_exif_from_json(src_im_path):
    exif = Image.Exif()
    json_path = f"{src_im_path}.json"
    image = Path(json_path)
    if not image.is_file():
        logging.warning(f"{json_path} does not exist")
        return exif
    js = json.loads(image.read_text())
    timestamp = int(js.get("creationTime", {}).get("timestamp"))
    exif[306] = format_ts_to_exif_mode(timestamp)
    return exif


def format_ts_to_exif_mode(timestamp):
    # timestamp => 2023:01:23 21:14:15
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y:%m:%d %H:%M:%S")

def main():
    global NO_EXIF
    configure_logging()
    folder_name = "im2" if len(sys.argv) < 2 else sys.argv[1]
    images = get_valid_images(folder_name)
    for src_im_path in images:
        dst_im_path = get_dest_path(src_im_path)
        compress_image(src_im_path)
        compressed_percentage = get_shrink_stats(src_im_path, dst_im_path)
        if compressed_percentage < 0:
            shutil.copy(src_im_path, dst_im_path)
            compressed_percentage = get_shrink_stats(src_im_path, dst_im_path)
        logging.debug(f"[{compressed_percentage:05.2f}] {src_im_path.name}")

    logging.info(f"NO EXIFS: {NO_EXIF}")


if __name__ == '__main__':
    NO_EXIF = 0
    main()
