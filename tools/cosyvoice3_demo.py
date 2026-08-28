#!/usr/bin/env python
"""CosyVoice 3 demo — voice clone из английских референсов.

Запуск ОБЯЗАТЕЛЬНО через venv CosyVoice (Python 3.10):
  C:\\tools\\cosyvoice3\\.venv\\Scripts\\python.exe tools/cosyvoice3_demo.py

Режимы:
  * single-part  — одна реплика (default, если у фразы 1 часть)
  * multi-part   — каждая часть своим голосом (speaker→ref), склейка с паузой
  * instruct     — эмоция/темп через instruction-промпт
  * sampling     — свои top_p/top_k/tau_r (RAS-семплер) через копию yaml
  * RL-веса      — llm.rl.pt вместо llm.pt (reward-posttrained)

Примеры:
  ... cosyvoice3_demo.py --guid ca2ef6c0-f159-447d-96d3-164e4ab8bb84        # Кунрад + нарратор
  ... cosyvoice3_demo.py --guid 958665ee-... --instruct angry
  ... cosyvoice3_demo.py --guid 958665ee-... --rl
  ... cosyvoice3_demo.py --guid 958665ee-... --sampling 0.9,50,0.1
  ... cosyvoice3_demo.py --text "Тест" --ref refs/samples_en_cosy/Narrator.wav --speed 0.9
"""

import argparse
import os
import shutil
import sys
import time

COSY_ROOT = r'C:\tools\cosyvoice3'
REPO_DIR = os.path.join(COSY_ROOT, 'CosyVoice')
MODEL_DIR = os.path.join(COSY_ROOT, 'pretrained_models', 'Fun-CosyVoice3-0.5B')
sys.path.insert(0, REPO_DIR)
sys.path.insert(0, os.path.join(REPO_DIR, 'third_party', 'Matcha-TTS'))

import torch
import torchaudio
import yaml
from cosyvoice.cli.cosyvoice import AutoModel

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
}

SPEAKER_REF_FALLBACK = {
    'narrator': 'refs/samples_en_cosy/Narrator.wav',
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


def hardlink_tree(src, dst):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isfile(s):
            if not os.path.exists(d):
                os.link(s, d)
        elif os.path.isdir(s):
            hardlink_tree(s, d)


def make_tuned_model_dir(top_p=None, top_k=None, tau_r=None, rl=False):
    tag = []
    if top_p is not None:
        tag.append('p{}'.format(top_p))
    if top_k is not None:
        tag.append('k{}'.format(top_k))
    if tau_r is not None:
        tag.append('t{}'.format(tau_r))
    if rl:
        tag.append('rl')
    dst = MODEL_DIR + ('_' + '_'.join(tag) if tag else '')
    if not os.path.exists(os.path.join(dst, 'cosyvoice3.yaml')):
        print('making tuned model dir:', dst)
        hardlink_tree(MODEL_DIR, dst)
    yaml_path = os.path.join(dst, 'cosyvoice3.yaml')
    with open(yaml_path, encoding='utf-8') as f:
        text = f.read()
    if top_p is not None:
        text = text.replace('top_p: 0.8', 'top_p: {}'.format(top_p))
    if top_k is not None:
        text = text.replace('top_k: 25', 'top_k: {}'.format(top_k))
    if tau_r is not None:
        text = text.replace('tau_r: 0.1', 'tau_r: {}'.format(tau_r))
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


def gen_one(cosyvoice, text, ref, speed, instruct):
    if instruct:
        instruct_text = INSTRUCT_MAP[instruct]
        print('instruct:', instruct, '|', instruct_text[:70])
        gen = cosyvoice.inference_instruct2(text, instruct_text, ref, stream=False, speed=speed, text_frontend=False)
    else:
        gen = cosyvoice.inference_cross_lingual(CV3_PREFIX + text, ref, stream=False, speed=speed, text_frontend=False)
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
    parser.add_argument('--instruct', choices=list(INSTRUCT_MAP), default=None)
    parser.add_argument('--sampling', default=None, help='top_p,top_k,tau_r (RAS-семплер)')
    parser.add_argument('--rl', action='store_true', default=True, help='использовать llm.rl.pt (default)')
    parser.add_argument('--base', action='store_true', help='использовать base llm.pt вместо RL')
    parser.add_argument('--gap', type=float, default=GAP, help='пауза между частями, сек')
    parser.add_argument('--single', action='store_true', help='только 1-ю часть фразы')
    args = parser.parse_args()

    if args.sampling:
        top_p, top_k, tau_r = (float(x) for x in args.sampling.split(','))
    else:
        top_p = top_k = tau_r = None
    rl = args.rl and not args.base
    model_dir = make_tuned_model_dir(top_p, top_k, tau_r, rl)

    if args.text:
        parts = [('manual', args.text)]
        args.guid = 'manual'
        refs = [args.ref]
    else:
        phrase = load_phrase(args.char, args.guid)
        parts = [(p.get('speaker'), p['text_clean']) for p in phrase.get('parts', []) if 'text_clean' in p]
        refs = [ref_for_speaker(sp) for sp, _ in parts]
        if args.single:
            parts, refs = parts[:1], refs[:1]

    base = os.path.join('output', 'cosyvoice3', args.char.lower())
    os.makedirs(base, exist_ok=True)
    out = args.out or os.path.join(base, '{}.wav'.format(args.guid))

    print('model  :', model_dir)
    print('out    :', out)

    t0 = time.time()
    cosyvoice = AutoModel(model_dir=model_dir)
    print('model loaded in {:.1f}s, sample_rate={}'.format(time.time() - t0, cosyvoice.sample_rate))

    pieces = []
    for i, ((speaker, text), ref) in enumerate(zip(parts, refs)):
        print('--- part {}: speaker={} ref={}'.format(i + 1, speaker, ref))
        print('    text: {}'.format(text))
        t1 = time.time()
        speech = gen_one(cosyvoice, text, ref, args.speed, args.instruct)
        pieces.append(speech)
        part_out = os.path.join(base, '{}__{}.wav'.format(args.guid, i + 1))
        torchaudio.save(part_out, speech, cosyvoice.sample_rate)
        print('    saved {} ({:.2f}s, rtf {:.2f})'.format(part_out, speech.shape[1] / cosyvoice.sample_rate, (time.time() - t1) / (speech.shape[1] / cosyvoice.sample_rate)))

    gap = torch.zeros(1, int(cosyvoice.sample_rate * args.gap))
    glued = pieces[0]
    for p in pieces[1:]:
        glued = torch.cat([glued, gap, p], dim=1)
    torchaudio.save(out, glued, cosyvoice.sample_rate)
    print('GLUED {} ({:.2f}s)'.format(out, glued.shape[1] / cosyvoice.sample_rate))


if __name__ == '__main__':
    main()
