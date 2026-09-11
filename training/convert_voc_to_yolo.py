"""
Converts the NEU-DET dataset (PASCAL VOC XML annotations) into YOLO format,
and splits it into train/val/test.

Source layout (after `git clone` into dataset/raw/):
    dataset/raw/IMAGES/*.jpg                    <- train+val image pool
    dataset/raw/ANNOTATIONS/*.xml                <- train+val label pool
    dataset/raw/Validation_Images/*.jpg          <- held-out test images
    dataset/raw/Validation_Annotations/*.xml     <- held-out test labels

Output layout (YOLO-ready):
    dataset/images/train/*.jpg
    dataset/images/val/*.jpg
    dataset/images/test/*.jpg
    dataset/labels/train/*.txt
    dataset/labels/val/*.txt
    dataset/labels/test/*.txt
    dataset/data.yaml
"""

import random
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

RANDOM_SEED = 42
VAL_SPLIT = 0.2  # fraction of the IMAGES/ANNOTATIONS pool held out for validation

DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
RAW_DIR = DATASET_DIR / "raw"

# Class names must exactly match the <name> tag used inside the XML files.
# Order here defines the YOLO class id (0-indexed).
CLASSES = [
    "crazing",
    "inclusion",
    "patches",
    "pitted_surface",
    "rolled-in_scale",
    "scratches",
]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}


def voc_to_yolo_box(xmin, ymin, xmax, ymax, img_w, img_h):
    """Convert VOC (xmin, ymin, xmax, ymax) pixel box to YOLO
    (x_center, y_center, width, height), all normalized 0-1."""
    x_center = (xmin + xmax) / 2.0 / img_w
    y_center = (ymin + ymax) / 2.0 / img_h
    width = (xmax - xmin) / img_w
    height = (ymax - ymin) / img_h
    return x_center, y_center, width, height


def convert_one_xml(xml_path: Path) -> str:
    """Parse one VOC XML file and return YOLO-format label text (one line per object)."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    size = root.find("size")
    img_w = float(size.find("width").text)
    img_h = float(size.find("height").text)

    lines = []
    for obj in root.findall("object"):
        class_name = obj.find("name").text.strip()
        if class_name not in CLASS_TO_ID:
            print(f"  WARNING: unknown class '{class_name}' in {xml_path.name}, skipping object")
            continue
        class_id = CLASS_TO_ID[class_name]

        box = obj.find("bndbox")
        xmin = float(box.find("xmin").text)
        ymin = float(box.find("ymin").text)
        xmax = float(box.find("xmax").text)
        ymax = float(box.find("ymax").text)

        xc, yc, w, h = voc_to_yolo_box(xmin, ymin, xmax, ymax, img_w, img_h)
        lines.append(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

    return "\n".join(lines)


def build_split(image_files, image_src_dir, ann_src_dir, images_out, labels_out):
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    converted, missing_xml = 0, 0
    for img_path in image_files:
        xml_path = ann_src_dir / (img_path.stem + ".xml")
        if not xml_path.exists():
            missing_xml += 1
            continue

        yolo_text = convert_one_xml(xml_path)

        shutil.copy2(img_path, images_out / img_path.name)
        (labels_out / (img_path.stem + ".txt")).write_text(yolo_text, encoding="utf-8")
        converted += 1

    return converted, missing_xml


def main():
    if not RAW_DIR.exists():
        raise SystemExit(
            f"ERROR: {RAW_DIR} not found. Clone the dataset first:\n"
            f"  git clone https://github.com/siddhartamukherjee/NEU-DET-Steel-Surface-Defect-Detection.git {RAW_DIR}"
        )

    random.seed(RANDOM_SEED)

    # --- Train/Val pool ---
    pool_images_dir = RAW_DIR / "IMAGES"
    pool_ann_dir = RAW_DIR / "ANNOTATIONS"
    pool_images = sorted(pool_images_dir.glob("*.jpg"))
    if not pool_images:
        raise SystemExit(f"ERROR: no .jpg images found in {pool_images_dir}")

    random.shuffle(pool_images)
    n_val = int(len(pool_images) * VAL_SPLIT)
    val_images = pool_images[:n_val]
    train_images = pool_images[n_val:]

    print(f"Train/Val pool: {len(pool_images)} images -> {len(train_images)} train / {len(val_images)} val")

    train_c, train_missing = build_split(
        train_images, pool_images_dir, pool_ann_dir,
        DATASET_DIR / "images" / "train", DATASET_DIR / "labels" / "train",
    )
    val_c, val_missing = build_split(
        val_images, pool_images_dir, pool_ann_dir,
        DATASET_DIR / "images" / "val", DATASET_DIR / "labels" / "val",
    )

    # --- Held-out test set (repo's own Validation_Images/Validation_Annotations) ---
    test_images_dir = RAW_DIR / "Validation_Images"
    test_ann_dir = RAW_DIR / "Validation_Annotations"
    test_c, test_missing = 0, 0
    if test_images_dir.exists():
        test_images = sorted(test_images_dir.glob("*.jpg"))
        test_c, test_missing = build_split(
            test_images, test_images_dir, test_ann_dir,
            DATASET_DIR / "images" / "test", DATASET_DIR / "labels" / "test",
        )
    else:
        print(f"NOTE: {test_images_dir} not found, skipping test split (you can create it manually later)")

    print("\n--- Conversion summary ---")
    print(f"train: {train_c} converted, {train_missing} missing XML")
    print(f"val:   {val_c} converted, {val_missing} missing XML")
    print(f"test:  {test_c} converted, {test_missing} missing XML")

    # --- data.yaml for YOLO training ---
    data_yaml = DATASET_DIR / "data.yaml"
    yaml_text = (
        f"path: {DATASET_DIR.as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"test: images/test\n"
        f"\n"
        f"nc: {len(CLASSES)}\n"
        f"names: {CLASSES}\n"
    )
    data_yaml.write_text(yaml_text, encoding="utf-8")
    print(f"\nWrote {data_yaml}")


if __name__ == "__main__":
    main()
