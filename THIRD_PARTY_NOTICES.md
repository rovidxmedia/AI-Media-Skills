# Third-party notices

The repository's MIT license applies to original project code and documentation. It does not replace the notices or terms attached to the following materials.

## RNNoise model data

- File: `skills/podcast-audio-repair/assets/cb.rnnn`
- Source: [Gregor Richards' rnnoise-models](https://github.com/GregorR/rnnoise-models/tree/master/conjoined-burgers-2018-08-28), conjoined-burgers model.
- Upstream [README](https://github.com/GregorR/rnnoise-models/blob/master/README.md) states that the model data, excluding its tools directory and README, is not subject to copyright.
- Included unmodified. SHA-256: `f1357c4e5be9dee8467bead486dfced2d75b640c26ad0b594fa7f102322371d9`.
- No upstream training data or tools are bundled.

## NARA-WPE 0.0.11

- Files: `skills/podcast-audio-repair/assets/python/nara_wpe/__init__.py` and `wpe.py`.
- Source: [fgnt/nara_wpe](https://github.com/fgnt/nara_wpe), version 0.0.11.
- Copyright (c) 2018 Communications Engineering Group, Paderborn University.
- License: MIT; the complete original notice is retained in [NARA-WPE-LICENSE.txt](skills/podcast-audio-repair/assets/NARA-WPE-LICENSE.txt).
- This repository distributes an unmodified subset, not the complete upstream package.

## Separately installed software

FFmpeg, Python, NumPy, SciPy, SoundFile, click, and their dependencies are installed independently and retain their respective upstream licenses. FFmpeg is not bundled; its build configuration affects its available filters and licensing. Refer to the [FFmpeg legal information](https://ffmpeg.org/legal.html) for its own distribution terms.
