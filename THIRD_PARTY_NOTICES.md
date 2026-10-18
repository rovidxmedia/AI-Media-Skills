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

## Optional video engines

Video Enhance downloads selected engines into a separate user cache. No executable, large model, upstream source archive or sample recording is bundled here. Pinned artifact URLs and SHA-256 values are in [engines.json](skills/video-enhance/references/engines.json).

- [Real-ESRGAN NCNN](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan) and [RIFE NCNN](https://github.com/nihui/rife-ncnn-vulkan) use MIT wrapper licenses and include separately attributed inference libraries and model resources. Preserve notices in the downloaded archives. The restoration package comes from the official [Real-ESRGAN release](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0).
- [SeedVR2 integration](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler) is installed at a pinned commit under its upstream license. Model weights and PyTorch dependencies retain their respective terms. Consult the source archive and model cards before redistributing them.
- FFmpeg's optional stabilization uses [vid.stab](https://github.com/georgmartius/vid.stab), installed as part of the chosen FFmpeg build rather than copied here.

The repository's MIT license covers the new orchestration scripts and guidance. It does not relicense downloaded engines, models or dependencies.

## Separately installed software

FFmpeg, Python, NumPy, SciPy, SoundFile, click, and their dependencies are installed independently and retain their respective upstream licenses. FFmpeg is not bundled; its build configuration affects its available filters and licensing. Refer to the [FFmpeg legal information](https://ffmpeg.org/legal.html) for its own distribution terms.
