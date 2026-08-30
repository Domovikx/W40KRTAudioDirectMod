#!/usr/bin/env python
"""CosyVoice 3 demo — voice clone из английских референсов.

Запуск ОБЯЗАТЕЛЬНО через venv CosyVoice (Python 3.10):
  C:\\tools\\cosyvoice3\\.venv\\Scripts\\python.exe tools/cosyvoice3_demo.py

Режимы:
  cross_lingual — CV3-префикс в тексте (старый базлайн)
  zero_shot     — метод офиц. HF Space: tgt без префикса, prompt_text =
                  'You are a helpful assistant.<|endofprompt|>' + транскрипт рефа
                  (транскрипт ищется в {ref}.txt)
  instruct2     — свободная инструкция (--instruct-text или --instruct)

Качество:
  --lang-token ru       — подставить <|ru|> перед целевым текстом
  --seed N              — seed (default: случайный, как в офиц. Space)
  --sampling p,k,tau    — RAS-семплер (копия yaml через hardlinks)
  --rl (default) / --base
  --speed
  Рефы предобрабатываются как в офиц. Space: librosa-trim тишины,
  пик 0.8, хвост 0.2с.

Примеры:
  ... cosyvoice3_demo.py --guid ca2ef6c0-f159-447d-96d3-164e4ab8bb84
  ... cosyvoice3_demo.py --guid 958665ee-... --mode zero_shot
  ... cosyvoice3_demo.py --guid 958665ee-... --mode cross_lingual --lang-token ru
  ... cosyvoice3_demo.py --guid 958665ee-... --mode instruct2 --instruct-text "You are a helpful assistant. Please speak in Russian, with a native accent.<|endofprompt|>"
"""

import argparse
import os
import random
import re
import shutil
import sys
import tempfile
import time

COSY_ROOT = r'C:\tools\cosyvoice3'
REPO_DIR = os.path.join(COSY_ROOT, 'CosyVoice')
MODEL_DIR = os.path.join(COSY_ROOT, 'pretrained_models', 'Fun-CosyVoice3-0.5B')
sys.path.insert(0, REPO_DIR)
sys.path.insert(0, os.path.join(REPO_DIR, 'third_party', 'Matcha-TTS'))

import numpy as np
import torch
import torchaudio
import yaml
from cosyvoice.cli.cosyvoice import AutoModel
from cosyvoice.utils.common import set_all_random_seed

DEFAULT_GUID = '958665ee-a30e-426e-9892-66068d7e47dd'
DEFAULT_CHAR = 'Kunrad_Voigtvir'
CV3_PREFIX = 'You are a helpful assistant.<|endofprompt|>'
GAP = 0.25

INSTRUCT_MAP = {
    'angry': 'You are a helpful assistant. 请非常生气地说一句话。<|endofprompt|>',
    'sad': 'You are a helpful assistant. 请非常伤心地说一句话。<|endofprompt|>',
    'happy': 'You are a helpful assistant. 请非常开心地说一句话。<|endofprompt|>',
    'fast': 'You are a helpful assistant. 请用尽可能快地语速说一句话。<|endofprompt|>',
    'slow': 'You are a helpful assistant. 请用尽可能慢地语速说一句话。<|endofprompt|>',
    'loud': 'You are a helpful assistant. Please say a sentence as loudly as possible.<|endofprompt|>',
    'soft': 'You are a helpful assistant. Please say a sentence in a very soft voice.<|endofprompt|>',
    'russian': 'You are a helpful assistant. Please speak in Russian, with a natural native accent.<|endofprompt|>',
}

SPEAKER_REF_FALLBACK = {
    'narrator': 'refs/samples_en_cosy/Narrator.wav',
    'Generic Male NPC': 'refs/samples_en_cosy/npc_m_1.wav',
    'Default NPC': 'refs/samples_en_cosy/npc_m_1.wav',
    'Generic Female NPC': 'refs/samples_en_cosy/npc_f_1.wav',
    'Seneschal (NPC)': 'refs/samples_en_cosy/Abelard_Werserian.wav',
}


def load_phrase(char, guid):
    catalog = os.path.join('catalog', 'people', '{}.yaml'.format(char))
    with open(catalog, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    for phrase in data.get('phrases', []):
        if phrase.get('guid') == guid:
            return phrase
    raise ValueError('guid {} не найден в {}'.format(guid, catalog))


def ref_for_speaker(speaker):
    if not speaker:
        raise ValueError('пустой speaker')
    cand = speaker.replace(' ', '_')
    path = os.path.join('refs', 'samples_en_cosy', '{}.wav'.format(cand))
    if os.path.exists(path):
        return path
    path2 = os.path.join('refs', 'samples_en_cosy', '{}.wav'.format(speaker))
    if os.path.exists(path2):
        return path2
    fallback = SPEAKER_REF_FALLBACK.get(speaker) or SPEAKER_REF_FALLBACK.get(cand)
    if fallback and os.path.exists(fallback):
        return fallback
    raise ValueError('нет референса для speaker={} (искал refs/samples_en_cosy/{}.wav)'.format(speaker, cand))


def prep_ref(path):
    """Постпроцессинг рефа как в офиц. HF Space: trim + peak 0.8 + 0.2s хвост.
    Аналог librosa.effects.trim (top_db=60, frame=440, hop=220) на numpy —
    без numba (librosa ломается на новых numba)."""
    speech, sr = torchaudio.load(path)
    if sr != 24000:
        speech = torchaudio.functional.resample(speech, sr, 24000)
    y = speech.squeeze(0).numpy()
    frame, hop = 440, 220
    if len(y) >= frame:
        n = 1 + (len(y) - frame) // hop
        idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
        rms = np.sqrt(np.mean(y[idx] ** 2, axis=1) + 1e-10)
        db = 20 * np.log10(rms + 1e-10)
        mask = db > (db.max() - 60)
        if mask.any():
            start = idx[mask.argmax(), 0]
            end = idx[len(mask) - mask[::-1].argmax() - 1, -1] + 1
            y = y[start:end]
    peak = float(np.abs(y).max())
    if peak > 0.8:
        y = y / peak * 0.8
    t = torch.from_numpy(y).unsqueeze(0)
    t = torch.cat([t, torch.zeros(1, int(24000 * 0.2))], dim=1)
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    torchaudio.save(tmp.name, t, 24000)
    return tmp.name


def link_tree(src, dst):
    """Hardlink-копия модель-дира, НО cosyvoice3.yaml — отдельная копия
    (чтобы правка сэмплинга в варианте не протекала в базовую модель)."""
    if not os.path.exists(dst):
        os.makedirs(dst)
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isfile(s):
            if os.path.exists(d):
                continue
            if name == 'cosyvoice3.yaml':
                shutil.copy2(s, d)
            else:
                os.link(s, d)
        elif os.path.isdir(s):
            link_tree(s, d)


def make_tuned_model_dir(top_p=None, top_k=None, tau_r=None, rl=False, cfg_rate=None):
    tag = []
    if top_p is not None:
        tag.append('p{}'.format(top_p))
    if top_k is not None:
        tag.append('k{}'.format(top_k))
    if tau_r is not None:
        tag.append('t{}'.format(tau_r))
    if cfg_rate is not None:
        tag.append('c{}'.format(cfg_rate))
    if rl:
        tag.append('rl')
    dst = MODEL_DIR + ('_' + '_'.join(tag) if tag else '')
    if not os.path.exists(os.path.join(dst, 'cosyvoice3.yaml')):
        print('making tuned model dir:', dst)
        link_tree(MODEL_DIR, dst)
    yaml_path = os.path.join(dst, 'cosyvoice3.yaml')
    with open(yaml_path, encoding='utf-8') as f:
        text = f.read()
    # re.sub по всему значению — идемпотентно (str.replace ломал yaml:
    # 'top_k: 25' -> 'top_k: 25.0' -> следующий прогон '25.0.0.0...')
    if top_p is not None:
        text = re.sub(r'top_p: [0-9.]+', 'top_p: {}'.format(top_p), text, count=1)
    if top_k is not None:
        text = re.sub(r'top_k: [0-9.]+', 'top_k: {}'.format(top_k), text, count=1)
    if tau_r is not None:
        text = re.sub(r'tau_r: [0-9.]+', 'tau_r: {}'.format(tau_r), text, count=1)
    if cfg_rate is not None:
        text = re.sub(r'inference_cfg_rate: [0-9.]+', 'inference_cfg_rate: {}'.format(cfg_rate), text, count=1)
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(text)
    if rl:
        llm_pt = os.path.join(dst, 'llm.pt')
        rl_pt = os.path.join(dst, 'llm.rl.pt')
        base_pt = os.path.join(dst, 'llm.base.pt')
        if os.path.exists(rl_pt) and not os.path.exists(base_pt):
            os.rename(llm_pt, base_pt)
            os.rename(rl_pt, llm_pt)
    return dst


def patch_flow_temperature(temp):
    """Проброс скрытого temperature в flow-диффузию (дефолт 1.0, в API не выведен).
    Сигнатура CV3-декодера: forward(mu, mask, n_timesteps, temperature=1.0,
    spks=None, cond=None, streaming=False)."""
    from cosyvoice.flow.flow_matching import CausalConditionalCFM
    orig = CausalConditionalCFM.forward

    def wrapped(self, mu, mask, n_timesteps, temperature=1.0, spks=None,
                cond=None, streaming=False, **kw):
        return orig(self, mu, mask, n_timesteps, temperature=temp, spks=spks,
                    cond=cond, streaming=streaming, **kw)

    CausalConditionalCFM.forward = wrapped


SILENT_TOKENS = frozenset({1, 2, 28, 29, 55, 248, 494, 2241, 2242, 2322, 2323})


def patch_silent_token_trim():
    """Срезать хвостовые silent/breath-токены перед flow.
    CV3 после фразы сам дорисовывает токены тишины/дыхания (FSQ silent and
    breath token), которые flow озвучивает как вздох/всхлип в конце реплики.
    Фильтр на уровне токенов не трогает речь (в отличие от аудио-трима)."""
    from cosyvoice.cli.model import CosyVoice3Model
    orig = CosyVoice3Model.token2wav

    def wrapped(self, token, *a, **kw):
        toks = token[0].tolist()
        i = len(toks)
        while i > 0 and toks[i - 1] in SILENT_TOKENS:
            i -= 1
        if i == 0:
            i = 1  # дегенерат: всё — тишина; оставляем 1 токен, чтобы flow не сломался
        return orig(self, token[:, :i], *a, **kw)

    CosyVoice3Model.token2wav = wrapped


def tail_trim_fade(wave, sr, fade_ms=60, thresh_db=-40.0):
    """Обрезать тихий хвост (вздохи/шум после речи) + fade-out.
    Порог −40дБ, fade 60мс. Дополнительно (2026-08-29): изолированные
    всплески после речи (вздох/клик громче порога через ≥40мс тишины)
    считаются артефактом и режутся до речи."""
    frame = max(int(sr * 0.01), 1)
    n = wave.shape[1] // frame
    if n < 2:
        return wave
    rms = []
    for i in range(n):
        seg = wave[:, i * frame:(i + 1) * frame]
        rms.append(float((seg ** 2).mean().sqrt()))
    rms = torch.tensor(rms)
    thr = 10 ** (thresh_db / 20)
    loud = rms > thr
    if not bool(loud.any()):
        return wave
    last = int(loud.nonzero().max())
    # изолированный хвостовой всплеск: ищем тихую лакуну перед последним
    # громким кадром; если ≥4 кадров (40мс) тишины между речью и всплеском —
    # всплеск артефакт, режем до речи
    q = last - 1
    while q >= 0 and not bool(loud[q]):
        q -= 1
    if q >= 0 and (last - 1 - q) >= 4:
        last = q
    end = min(wave.shape[1], (last + 1) * frame + int(sr * 0.03))
    wave = wave[:, :end]
    f = int(sr * fade_ms / 1000)
    if f > 0 and wave.shape[1] > f * 2:
        env = torch.linspace(1.0, 0.0, f)
        wave = torch.cat([wave[:, :-f], wave[:, -f:] * env], dim=1)
    return wave


def gen_one(cosyvoice, text, ref, args):
    prepped = prep_ref(ref)
    if args.seed is None:
        seed = random.randint(1, 100000000)
    else:
        seed = args.seed
    set_all_random_seed(seed)
    tgt = text
    if args.lang_token:
        tgt = '<|{}|>{}'.format(args.lang_token, tgt)
    if args.mode == 'zero_shot':
        transcript_path = os.path.splitext(ref)[0] + '.txt'
        if not os.path.exists(transcript_path):
            raise ValueError('для zero_shot нужен транскрипт {}.txt'.format(ref))
        with open(transcript_path, encoding='utf-8') as f:
            transcript = f.read().strip()
        prompt_text = CV3_PREFIX + transcript
        print('    prompt_text: {}'.format(prompt_text[:90]))
        gen = cosyvoice.inference_zero_shot(tgt, prompt_text, prepped, stream=False, speed=args.speed, text_frontend=False)
    elif args.mode == 'instruct2':
        instruct_text = args.instruct_text or INSTRUCT_MAP[args.instruct or 'russian']
        print('    instruct: {}'.format(instruct_text[:90]))
        gen = cosyvoice.inference_instruct2(tgt, instruct_text, prepped, stream=False, speed=args.speed, text_frontend=False)
    else:
        gen = cosyvoice.inference_cross_lingual(CV3_PREFIX + tgt, prepped, stream=False, speed=args.speed, text_frontend=False)
    for j in gen:
        return j['tts_speech']


def main():
    parser = argparse.ArgumentParser(description='CosyVoice 3 voice-clone demo')
    parser.add_argument('--guid', default=DEFAULT_GUID)
    parser.add_argument('--char', default=DEFAULT_CHAR)
    parser.add_argument('--text', default=None, help='одиночная реплика вместо каталога')
    parser.add_argument('--ref', default='refs/samples_en_cosy/Kunrad_Voigtvir.wav')
    parser.add_argument('--out', default=None)
    parser.add_argument('--speed', type=float, default=1.0)
    parser.add_argument('--mode', choices=['cross_lingual', 'zero_shot', 'instruct2'], default='cross_lingual')
    parser.add_argument('--instruct', choices=list(INSTRUCT_MAP), default=None)
    parser.add_argument('--instruct-text', default=None, help='свободная инструкция для instruct2')
    parser.add_argument('--lang-token', default=None, help='например ru — подставить <|ru|> перед текстом')
    parser.add_argument('--seed', type=int, default=42, help='default: 42 (победный конфиг)')
    parser.add_argument('--sampling', default='0.5,10,0.15', help='top_p,top_k,tau_r (RAS, победный дефолт 0.5,10,0.15)')
    parser.add_argument('--cfg', type=float, default=0.9, help='inference_cfg_rate (победный дефолт 0.9; сток модели 0.7)')
    parser.add_argument('--flow-temp', type=float, default=1.2, help='temperature flow-диффузии (победный дефолт 1.2; сток кода 1.0)')
    parser.add_argument('--rl', action='store_true', default=True, help='использовать llm.rl.pt (default)')
    parser.add_argument('--base', action='store_true', help='использовать base llm.pt вместо RL')
    parser.add_argument('--gap', type=float, default=GAP, help='пауза между частями, сек')
    parser.add_argument('--single', action='store_true', help='только 1-ю часть фразы')
    parser.add_argument('--tail-trim', action=argparse.BooleanOptionalAction, default=False, help='обрезка хвоста + fade (default: OFF — перерезает слова, детектор артефактов в разработке)')
    parser.add_argument('--fade-ms', type=int, default=60, help='длина fade-out при --tail-trim')
    parser.add_argument('--s16', action=argparse.BooleanOptionalAction, default=True, help='сохранять PCM s16 (default: on, для Localization)')
    parser.add_argument('--no-silent-trim', action='store_true', help='НЕ срезать хвостовые silent/breath-токены')
    args = parser.parse_args()

    if args.sampling:
        top_p, top_k, tau_r = (float(x) for x in args.sampling.split(','))
    else:
        top_p = top_k = tau_r = None
    rl = args.rl and not args.base
    model_dir = make_tuned_model_dir(top_p, top_k, tau_r, rl, cfg_rate=args.cfg)

    if args.text:
        parts = [('manual', args.text)]
        args.guid = 'manual'
        refs = [args.ref]
    else:
        phrase = load_phrase(args.char, args.guid)
        parts = [(p.get('speaker_override') or p.get('speaker'), p['text_clean']) for p in phrase.get('parts', []) if 'text_clean' in p]
        refs = [ref_for_speaker(sp) for sp, _ in parts]
        if args.single:
            parts, refs = parts[:1], refs[:1]

    base = os.path.join('output', 'cosyvoice3', args.char.lower())
    os.makedirs(base, exist_ok=True)
    out = args.out or os.path.join(base, '{}.wav'.format(args.guid))

    print('model  :', model_dir)
    print('mode   :', args.mode, '| lang-token:', args.lang_token, '| seed:', args.seed)
    print('out    :', out)

    t0 = time.time()
    cosyvoice = AutoModel(model_dir=model_dir)
    if args.flow_temp is not None:
        patch_flow_temperature(args.flow_temp)
        print('flow temperature patched:', args.flow_temp)
    if not args.no_silent_trim:
        patch_silent_token_trim()
        print('silent/breath token trim: ON')
    print('model loaded in {:.1f}s, sample_rate={}'.format(time.time() - t0, cosyvoice.sample_rate))

    pieces = []
    for i, ((speaker, text), ref) in enumerate(zip(parts, refs)):
        print('--- part {}: speaker={} ref={}'.format(i + 1, speaker, ref))
        print('    text: {}'.format(text))
        t1 = time.time()
        speech = gen_one(cosyvoice, text, ref, args)
        if args.tail_trim:
            speech = tail_trim_fade(speech, cosyvoice.sample_rate, fade_ms=args.fade_ms)
        pieces.append(speech)
        if args.out:
            part_out = args.out[:-4] + '__{}.wav'.format(i + 1)
        else:
            part_out = os.path.join(base, '{}__{}.wav'.format(args.guid, i + 1))
        torchaudio.save(part_out, speech, cosyvoice.sample_rate)
        print('    saved {} ({:.2f}s, rtf {:.2f})'.format(part_out, speech.shape[1] / cosyvoice.sample_rate, (time.time() - t1) / (speech.shape[1] / cosyvoice.sample_rate)))

    gap = torch.zeros(1, int(cosyvoice.sample_rate * args.gap))
    glued = pieces[0]
    for p in pieces[1:]:
        glued = torch.cat([glued, gap, p], dim=1)
    if args.s16:
        torchaudio.save(out, glued, cosyvoice.sample_rate, encoding='PCM_S', bits_per_sample=16)
    else:
        torchaudio.save(out, glued, cosyvoice.sample_rate)
    print('GLUED {} ({:.2f}s)'.format(out, glued.shape[1] / cosyvoice.sample_rate))


if __name__ == '__main__':
    main()
