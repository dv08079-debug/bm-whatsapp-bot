"""Latvian voiceover for the clinic demo, synthesized offline with Piper.

Needs sherpa-onnx<2 (pip) and the voice from
https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-lv_LV-aivars-medium.tar.bz2

Usage: python3 voiceover.py <model_dir>   -> seg0.wav ... seg3.wav
Segments are placed at 0.3 s, 6.6 s, 22.0 s and 41.9 s, and the music is
ducked under the voice with ffmpeg sidechaincompress.
"""
import sys
import wave

import numpy as np
import sherpa_onnx

M = sys.argv[1]
cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(vits=sherpa_onnx.OfflineTtsVitsModelConfig(
    model=f'{M}/lv_LV-aivars-medium.onnx', tokens=f'{M}/tokens.txt', data_dir=f'{M}/espeak-ng-data'), num_threads=4))
tts = sherpa_onnx.OfflineTts(cfg)

# Brand names are spelled phonetically so the Latvian voice reads them right.
SEGMENTS = [
    ("Pulkstenis ir desmit vakarā. Pacients vēlas pierakstīties pie ārsta, bet reģistratūra jau ir slēgta.", 1.1),
    ("Ar Baltik Maind mākslīgā intelekta administratoru pacients vienkārši uzraksta Vatsapā. "
     "Asistents atbild dažās sekundēs, piedāvā brīvos laikus un pieraksta pie ārsta.", 1.0),
    ("Pirms vizītes tas nosūta atgādinājumu, tāpēc mazāk neieradušos pacientu. "
     "Asistents sazinās latviski, krieviski un angliski, un sarežģītus jautājumus nodod administratoram.", 1.0),
    ("Pieraksts vienā minūtē. Bez zvaniem un rindām. Baltik Maind. Uzziniet vairāk: baltik maind punkts el vē.", 1.1),
]

for i, (text, speed) in enumerate(SEGMENTS):
    audio = tts.generate(text, sid=0, speed=speed)
    x = np.array(audio.samples, dtype=np.float32)
    with wave.open(f'seg{i}.wav', 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(audio.sample_rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
