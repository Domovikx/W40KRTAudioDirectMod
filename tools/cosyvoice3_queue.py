#!/usr/bin/env python
"""Очередь генерации CosyVoice 3 — все персонажи из каталога.

Запуск:
    C:\tools\cosyvoice3\.venv\Scripts\python.exe tools/cosyvoice3_queue.py

Resumable: пропускает персонажей у которых >= фраз в ruRU_cosy.
Лог: output/cosyvoice3/queue.log
"""
import os
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = r'C:\tools\cosyvoice3\.venv\Scripts\python.exe'
BATCH = os.path.join(ROOT, 'tools', 'cosyvoice3_batch.py')
LOG = os.path.join(ROOT, 'output', 'cosyvoice3', 'queue.log')

QUEUE = [
    ('Cassia_Orsellio', 656),
    ('Solomon_Antar', 607),
    ('Kibellah', 579),
    ('Marazhai_Aezyrraesh', 553),
    ('Idira_Tlass', 412),
    ('Heinrix_van_Calox', 410),
    ('Pasqal_Haneumann', 408),
    ('Abelard_Werserian', 404),
    ('Sister_Argenta', 382),
    ('Ulfar', 358),
    ('Yrliet_Lanaeviss', 329),
    ('Jae_Heydari', 248),
    ('Eogann', 207),
    ('Manipulus', 204),
    ('Smuggler', 179),
    ('Seneschal_NPC', 105),
    ('Psyker_NPC', 97),
    ('Trazyn', 66),
    ('Narrator', 4478),
    ('Generic_Male_NPC', 24862),
]


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def count_wav(char_name):
    d = os.path.join(ROOT, 'Localization', 'ruRU_cosy', char_name)
    if not os.path.isdir(d):
        return 0
    return len([f for f in os.listdir(d) if f.endswith('.wav')])


def run_char(char_name, total):
    done = count_wav(char_name)
    if done >= total:
        log(f'SKIP {char_name}: {done}/{total} already done')
        return True

    log(f'START {char_name}: {done}/{total} remaining={total - done}')
    cmd = [PYTHON, BATCH, '--char', char_name, '--force']
    try:
        proc = subprocess.Popen(
            cmd, cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace'
        )
        last_line = ''
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                last_line = line
        rc = proc.wait(timeout=14400)  # 4ч safety timeout
        if rc == 0 and 'done=' in last_line:
            log(f'DONE {char_name}: {last_line}')
            return True
        else:
            log(f'WARN {char_name}: rc={rc} last={last_line}')
            return rc == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        log(f'TIMEOUT {char_name}: killed after 4h')
        return False
    except Exception as e:
        log(f'ERROR {char_name}: {e}')
        return False


def main():
    log('=== Queue started ===')
    total_done = 0
    for char_name, total in QUEUE:
        done = count_wav(char_name)
        if done >= total:
            log(f'SKIP {char_name}: {done}/{total}')
            total_done += 1
            continue

        success = run_char(char_name, total)
        if not success:
            log(f'PAUSE at {char_name} — restart to continue')
            break
        total_done += 1

    log(f'=== Queue finished: {total_done}/{len(QUEUE)} chars ===')


if __name__ == '__main__':
    main()
