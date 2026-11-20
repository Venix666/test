import pytest

from halcyon.limits import ValidationError, validate


def grading(**midtones):
    return {
        "format_version": "1.21.90",
        "minecraft:color_grading_settings": {
            "description": {"identifier": "test:grade"},
            "color_grading": {"midtones": midtones},
            "tone_mapping": {"operator": "aces"},
        },
    }


def test_valid_document_passes():
    validate(grading(saturation=[1.2, 1.2, 1.2]))


@pytest.mark.parametrize("doc", [
    grading(saturation=[11.0, 1.0, 1.0]),                       # saturation max 10
    grading(contrast=[1.0, 1.0]),                               # vec3 required
    {**grading(), "format_version": 1},                         # version string
])
def test_out_of_range_values_fail(doc):
    with pytest.raises(ValidationError):
        validate(doc)


def test_identifier_must_be_namespaced():
    doc = grading()
    doc["minecraft:color_grading_settings"]["description"]["identifier"] = "no_namespace"
    with pytest.raises(ValidationError):
        validate(doc)


def test_unknown_tonemapper_fails():
    doc = grading()
    doc["minecraft:color_grading_settings"]["tone_mapping"]["operator"] = "filmic"
    with pytest.raises(ValidationError, match="operator"):
        validate(doc)


def test_fog_heights_must_be_ordered():
    doc = {
        "format_version": "1.21.90",
        "minecraft:fog_settings": {
            "description": {"identifier": "test:fog"},
            "volumetric": {"density": {"air": {"max_density": 0.1, "max_density_height": 200,
                                               "zero_density_height": 100}}},
        },
    }
    with pytest.raises(ValidationError, match="zero_density_height"):
        validate(doc)


def test_lighting_keyframes_checked():
    doc = {
        "format_version": "1.21.80",
        "minecraft:lighting_settings": {
            "description": {"identifier": "test:light"},
            "ambient": {"color": {"0.0": [255, 255, 300]}, "illuminance": 0.1},
        },
    }
    with pytest.raises(ValidationError, match="300"):
        validate(doc)
