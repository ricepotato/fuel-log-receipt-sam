import json
import os
import sys

import pytest

os.environ.setdefault("RECEIPT_BUCKET", "test-bucket")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../analyze"))

from app import analyze_image  # noqa: E402

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../.test_data")

EXT_TO_MEDIA_TYPE = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}

TEST_IMAGES = [
    "image1.jpeg",
    "image2.jpg",
    "image4.jpeg",
    "image5.jpeg",
    "image6.jpeg",
]


def load_test_case(image_filename: str):
    stem = image_filename.rsplit(".", 1)[0]
    image_path = os.path.join(TEST_DATA_DIR, image_filename)
    json_path = os.path.join(TEST_DATA_DIR, f"{stem}.json")
    ext = image_filename.rsplit(".", 1)[-1].lower()
    media_type = EXT_TO_MEDIA_TYPE.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    with open(json_path, "r", encoding="utf-8") as f:
        expected = json.load(f)
    return image_bytes, media_type, expected


@pytest.mark.parametrize("image_filename", TEST_IMAGES)
def test_analyze_image(image_filename):
    image_bytes, media_type, expected = load_test_case(image_filename)

    result = analyze_image(image_bytes, media_type)

    assert isinstance(result, dict), "결과가 dict여야 합니다"

    assert result.get("date") == expected["date"], (
        f"date 불일치: {result.get('date')} != {expected['date']}"
    )
    assert result.get("location") == expected["location"], (
        f"location 불일치: {result.get('location')} != {expected['location']}"
    )
    assert result.get("totalPrice") == expected["totalPrice"], (
        f"totalPrice 불일치: {result.get('totalPrice')} != {expected['totalPrice']}"
    )

    if expected["liters"] is not None:
        assert result.get("liters") == pytest.approx(expected["liters"], rel=0.01), (
            f"liters 불일치: {result.get('liters')} != {expected['liters']}"
        )

    if expected["pricePerLiter"] is not None:
        assert result.get("pricePerLiter") == pytest.approx(
            expected["pricePerLiter"], abs=5
        ), (
            f"pricePerLiter 불일치: {result.get('pricePerLiter')} != {expected['pricePerLiter']}"
        )
