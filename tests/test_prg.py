import colorsys
import hashlib

import numpy as np
import pytest

import canvas_size
import palettes
import registry
from batch import BatchSpec, build_config, run_batch
from core import Config, generate


def small(**kw):
    base = dict(size=(320, 200), shapes=(6, 8), effects=[])
    base.update(kw)
    return Config(**base)


def digest(img):
    return hashlib.sha256(img.tobytes()).hexdigest()


def test_parse_size_presets_and_custom():
    assert canvas_size.parse_size("fhd") == (1920, 1080)
    assert canvas_size.parse_size("1500x900") == (1500, 900)
    assert canvas_size.parse_size("800×600") == (800, 600)


@pytest.mark.parametrize("bad", ["10x10", "abc", "99999x100", "0x0", "20000x20000"])
def test_parse_size_errors(bad):
    with pytest.raises(ValueError):
        canvas_size.parse_size(bad)


def test_random_size_is_deterministic():
    a = canvas_size.resolve_size("random", np.random.default_rng(5))
    b = canvas_size.resolve_size("random", np.random.default_rng(5))
    assert a == b


def test_plugins_registered():
    registry.load_plugins()
    assert {"circle", "blob", "wave", "crescent", "arc", "cross", "flower", "gear", "drop", "spiral", "zigzag", "rounded_rect"} <= set(registry.SHAPES)
    assert {"shadow", "glow", "grain", "bloom"} <= set(registry.EFFECTS)


def test_custom_plugin_registration():
    registry.load_plugins()

    @registry.register_effect("_test_invert")
    def invert(img, rng, unit, amount=1.0):
        from PIL import ImageChops
        return ImageChops.invert(img)

    try:
        assert registry.parse_effects("_test_invert:amount=2")[0] == ("_test_invert", {"amount": 2.0})
        img, _ = generate(small(effects=[("_test_invert", {})]), 1)
        base, _ = generate(small(), 1)
        assert digest(img) != digest(base)
    finally:
        registry.EFFECTS.pop("_test_invert")


def test_parse_effects_errors():
    with pytest.raises(ValueError):
        registry.parse_effects("nosuch")
    with pytest.raises(ValueError):
        registry.parse_effects("glow:bogus=1")
    with pytest.raises(ValueError):
        registry.parse_effects("glow:radius=abc")


def test_output_size_exact():
    img, _ = generate(small(size=(333, 217)), 3)
    assert img.size == (333, 217)


def test_deterministic_same_seed_and_differs_between_seeds():
    cfg = small(effects=registry.parse_effects("shadow,glow,grain,vignette,warp"))
    a, _ = generate(cfg, 42)
    b, _ = generate(cfg, 42)
    c, _ = generate(cfg, 43)
    assert digest(a) == digest(b)
    assert digest(a) != digest(c)


@pytest.mark.parametrize("fx", ["shadow", "glow"])
def test_element_effects_change_pixels(fx):
    base, _ = generate(small(palette="ocean"), 9)
    with_fx, _ = generate(small(palette="ocean", effects=registry.parse_effects(fx)), 9)
    assert digest(base) != digest(with_fx)


def test_every_effect_runs():
    registry.load_plugins()
    for name in registry.EFFECTS:
        img, _ = generate(small(effects=[(name, {})]), 2)
        assert img.size == (320, 200)


def test_dominant_hue():
    cfg = small(size=(400, 300), hue=30, scheme="mono", bg="dark", shapes=(25, 25))
    img, _ = generate(cfg, 11)
    arr = np.asarray(img, dtype=np.float32) / 255
    # берём только достаточно насыщенные и не тёмные пиксели
    hsv = np.asarray(img.convert("HSV")).reshape(-1, 3)
    mask = (hsv[:, 1] > 60) & (hsv[:, 2] > 60)
    assert mask.sum() > 1000
    hue = hsv[mask, 0].astype(float) * 360 / 256
    dist = np.minimum(abs(hue - 30), 360 - abs(hue - 30))
    assert np.median(dist) < 15


def test_dominance_weights():
    rng = np.random.default_rng(0)
    pal = palettes.from_dominant((51, 102, 255), rng, "complementary", dominance=0.7)
    h0 = colorsys.rgb_to_hls(51 / 255, 102 / 255, 1.0)[0]
    share = 0.0
    for c, w in zip(pal.colors, pal._p):
        h, _, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
        d = min(abs(h - h0), 1 - abs(h - h0))
        if d < 0.05 and s > 0.4:  # светлый малонасыщенный «блик» в счёт не идёт
            share += w
    assert share == pytest.approx(0.7, abs=0.05)


def test_batch_files_and_reproducibility(tmp_path):
    spec = BatchSpec(size="random", shapes=(4, 6), variations=True, palette="random")
    metas = run_batch(spec, 3, 100, str(tmp_path / "a"), workers=2)
    assert len(metas) == 3
    assert len(list((tmp_path / "a").glob("*.png"))) == 3
    assert len(list((tmp_path / "a").glob("*.json"))) == 3
    run_batch(spec, 1, 101, str(tmp_path / "b"), workers=1)  # seed второго изображения
    a = (tmp_path / "a" / "prg_0001_s101.png").read_bytes()
    b = (tmp_path / "b" / "prg_0000_s101.png").read_bytes()
    assert a == b


def test_build_config_bad_size():
    with pytest.raises(ValueError):
        build_config(BatchSpec(size="5x5"), 1)
