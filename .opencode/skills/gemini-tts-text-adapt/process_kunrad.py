#!/usr/bin/env python3
"""Process Кунрад_Войгтвир.yaml: generate gemini_text for null entries."""

import yaml
import re
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
YAML_PATH = os.path.join(REPO_DIR, 'catalog', 'people', 'Кунрад_Войгтвир.yaml')

# Character configs
CHARACTERS = {
    'Кунрад Войгтвир': {
        'gender': 'M',
        'personality': 'коварный, манипулятивный, вкрадчивый',
        'voice': 'aidar',
        'gemini_voice': 'Sadaltager',
        'default_tags': ['sly'],
    },
    'Теодора фон Валанциус': {
        'gender': 'F',
        'personality': 'властная, жёсткая, решительная',
        'voice': 'xenia',
        'gemini_voice': 'Kore',
        'default_tags': ['firm'],
    },
}

FILE_OWNER = 'Кунрад Войгтвир'
FILE_GENDER = 'M'


def resolve_mf(text, gender):
    def repl(m):
        parts = m.group(1).split('|')
        if len(parts) >= 2:
            return parts[0] if gender == 'M' else parts[1]
        return ''
    return re.sub(r'\{mf\|([^}]*)\}', repl, text)


def resolve_rt_mf(text, gender):
    def repl(m):
        parts = m.group(1).split('|')
        if len(parts) >= 2:
            return parts[0] if gender == 'M' else parts[1]
        return ''
    return re.sub(r'\{rt_mf\|([^}]*)\}', repl, text)


def resolve_name_in_text(text, phrase_full_text):
    """Replace {name} with 'лорд-капитан' or omit if already present."""
    if '{name}' not in text:
        return text

    # Get dialog parts (text outside {n} blocks) to check for Лорд-капитан
    dialog = re.sub(r'\{n\}.*?\{/n\}', '', phrase_full_text)
    # Check if "Лорд-капитан" (or inflected forms) appear in dialog addressing player
    has_lord_in_dialog = bool(re.search(r'Лорд-капитан[ауом]?', dialog))

    if has_lord_in_dialog:
        # Check if it refers to Теодора (i.e. "Лорд-капитан Теодора")
        if 'Теодор' in dialog or 'Леди' in dialog:
            # Refers to Теодора, replace {name}
            return re.sub(r'\{name\}', 'лорд-капитан', text)
        else:
            # Already addresses player, omit {name}
            return re.sub(r'\{name\}', '', text)
    else:
        return re.sub(r'\{name\}', 'лорд-капитан', text)


def clean_one_phrase(text, gender):
    """Apply markup resolution to text (before final assembly)."""
    # Resolve mf tags with gender
    text = resolve_mf(text, gender)
    text = resolve_rt_mf(text, gender)
    # Strip {g|...} and {/g}
    text = re.sub(r'\{g\|[^}]*\}', '', text)
    text = re.sub(r'\{/g\}', '', text)
    # Strip {d|...} and {/d}
    text = re.sub(r'\{d\|[^}]*\}', '', text)
    text = re.sub(r'\{/d\}', '', text)
    # {name} is handled separately
    # {n}...{/n} stays verbatim — we keep it
    return text


def infer_speaker(phrase):
    """Infer speaker when speaker field is null."""
    text = phrase['text']
    event = phrase.get('event', '')

    # Check {n} blocks for character mentions
    n_blocks = re.findall(r'\{n\}(.*?)\{/n\}', text)

    # If Теодора is explicitly acting in narration = she's speaking
    for nb in n_blocks:
        if 'Теодор' in nb and ('бросает взгляд' in nb or 'шипит' in nb or 'гневно' in nb or
                                'машет' in nb or 'указывает' in nb or 'качает головой' in nb or
                                'нетерпеливо' in nb or 'задумчивый взгляд' in nb):
            return 'Теодора фон Валанциус'
        if 'Вольного Торговца' in nb or 'Вольный Торговец' in nb:
            return 'Теодора фон Валанциус'

    # If Морт is acting or dialog is addressed to Кунрад by name
    for nb in n_blocks:
        if 'Морт' in nb and ('оглядывается' in nb or 'проверяет' in nb or 'вытаскивает' in nb):
            return 'Морт'

    # Check dialog text for addressing Кунрад
    if 'пунктуальный, Кунрад' in text or 'нарисовался' in text:
        return 'Морт'

    # Check dialog for "Мастер шепотов" addressing (Теодора)
    dialog = re.sub(r'\{n\}.*?\{/n\}', '', text).strip()
    if 'Мастер шепотов' in dialog:
        # Check if it's commanding/angry tone or giving orders
        if any(x in text for x in ['Довольно!', 'что творится на моем корабле', 'не должен допустить', 'Делайте что угодно']):
            return 'Теодора фон Валанциус'

    # Check if text addresses speaker with commands ("Мастер шепотов, ...")
    if re.search(r'Мастер шепотов,', dialog) and re.search(r'[!?]', dialog):
        return 'Теодора фон Валанциус'

    # Default: file owner
    return FILE_OWNER


def get_emotion_tags_from_narration(text, default_tags):
    """Extract emotion tags from {n} blocks, returning new tags list."""
    tags = list(default_tags)
    n_blocks = re.findall(r'\{n\}(.*?)\{/n\}', text, re.DOTALL)

    for nb in n_blocks:
        nb_lower = nb.lower()

        # Laughter / amusement
        if any(w in nb_lower for w in ['смеет', 'усмеха', 'смешк', 'хохоч']):
            if 'chuckles' not in tags:
                tags.append('chuckles')
        if any(w in nb_lower for w in ['улыба', 'лукав']):
            if 'amused' not in tags:
                tags.append('amused')
        # Anger / frustration
        if any(w in nb_lower for w in ['злобн', 'ярост', 'гневн', 'ненавист', 'белеет']):
            if 'frustration' not in tags:
                tags.append('frustration')
        if 'шипит' in nb_lower:
            if 'frustration' not in tags:
                tags.append('frustration')
        # Sigh
        if any(w in nb_lower for w in ['вздыха', 'выдыха', 'облегчен']):
            if 'sighs' not in tags:
                tags.append('sighs')
        # Whisper
        if any(w in nb_lower for w in ['вкрадчив', 'осторож']):
            if 'whispers' not in tags:
                tags.append('whispers')
        # Serious
        if any(w in nb_lower for w in ['серьезн', 'серьёзн']):
            if 'serious' not in tags:
                tags.append('serious')
        # Curious
        if any(w in nb_lower for w in ['заинтриг', 'заинтересов']):
            if 'curious' not in tags:
                tags.append('curious')

    return tags


def process_phrase(phrase):
    """Process a single phrase and return gemini_text."""
    raw_text = phrase['text']
    speaker = phrase.get('speaker') or infer_speaker(phrase)

    # Determine gender and default tags for the speaker
    if speaker in CHARACTERS:
        gender = CHARACTERS[speaker]['gender']
        default_tags = list(CHARACTERS[speaker]['default_tags'])
    elif speaker == FILE_OWNER:
        gender = FILE_GENDER
        default_tags = ['sly']
    elif speaker == 'Морт':
        gender = 'M'
        default_tags = ['neutral']
    else:
        gender = FILE_GENDER
        default_tags = ['neutral']

    # 1. Resolve {name} first (we need original text for context checks)
    text_with_name = resolve_name_in_text(raw_text, raw_text)

    # 2. Resolve other markup
    cleaned = clean_one_phrase(text_with_name, gender)

    # 3. Normalize whitespace: collapse \n and extra spaces
    cleaned = re.sub(r'\s*\n\s*', ' ', cleaned)
    cleaned = re.sub(r' +', ' ', cleaned)

    # 4. Remove dialog framing quotes, preserve inner quotes like "Лорд-капитан"
    # Strategy: split into {n} blocks and dialog segments; strip framing " from each dialog segment
    cleaned = cleaned.strip()
    segments = re.split(r'(\{n\}.*?\{/n\})', cleaned)
    result_segments = []
    for seg in segments:
        if seg.startswith('{n}') and seg.endswith('{/n}'):
            result_segments.append(seg)
        else:
            # Dialog segment: strip leading/trailing framing quotes
            seg = seg.strip()
            # Remove leading " if followed by text (dialog opening)
            if seg.startswith('"') and len(seg) > 1:
                seg = seg[1:]
            # Remove trailing " if preceded by text (dialog closing) — but only if " is at the end
            # Handle patterns like '".', '"?', '"!', '",', '"...', or just '"'
            while seg.endswith('"') and seg.rstrip('"').endswith((' ', '.', ',', '!', '?', '…', '-', '—')):
                # This " might be a closing quote after punctuation
                # Check if preceding content is text (not a {n} reference)
                seg = seg[:-1]
            # If all that's left is just " at end
            if seg.endswith('"') and not seg.endswith('""'):
                seg = seg[:-1]
            result_segments.append(seg)
    cleaned = ''.join(result_segments)

    # 5. Add audio tags
    tags = get_emotion_tags_from_narration(raw_text, default_tags)
    if tags:
        tag_str = '[' + '] ['.join(tags) + '] '
        gemini_text = tag_str + cleaned
    else:
        gemini_text = cleaned

    # 6. Final whitespace compress
    gemini_text = re.sub(r' +', ' ', gemini_text).strip()
    gemini_text = re.sub(r'\s+\.', '.', gemini_text)  # fix space before period
    gemini_text = re.sub(r'\s+,', ',', gemini_text)    # fix space before comma
    gemini_text = re.sub(r'\s+!', '!', gemini_text)
    gemini_text = re.sub(r'\s+\?', '?', gemini_text)
    gemini_text = re.sub(r'\s+\.\.\.', '...', gemini_text)  # fix space before ellipsis
    gemini_text = re.sub(r'\.\.\.(\w)', lambda m: '... ' + m.group(1), gemini_text)  # space after ellipsis if followed by word

    return gemini_text, speaker


def main():
    print(f"Reading {YAML_PATH}")
    with open(YAML_PATH, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    phrases = data['phrases']
    total = len(phrases)
    processed = 0
    skipped = 0
    issues = []

    for i, phrase in enumerate(phrases):
        if phrase.get('gemini_text') is not None:
            skipped += 1
            continue

        try:
            gemini_text, speaker = process_phrase(phrase)
            phrase['gemini_text'] = gemini_text
            processed += 1

            # Verify no text loss: compare content chars only (ignore tags/quotes/brackets)
            old_clean = re.sub(r'\{[^}]*\}', '', phrase['text'])
            old_clean = re.sub(r'[\s"\'{}]', '', old_clean)
            # Normalize {name} → лордкапитан for fair comparison
            old_clean = old_clean.replace('{name}', 'лордкапитан')
            new_clean = re.sub(r'\[.*?\]\s*', '', gemini_text)
            new_clean = re.sub(r'[\s"\'{}]', '', new_clean)

            if old_clean != new_clean:
                issues.append(
                    f"  PHRASE {i+1} ({phrase['guid'][:8]}): TEXT LOSS? "
                    f"old=[{old_clean}] vs new=[{new_clean}]"
                )

            print(f"  [{i+1}/{total}] {phrase['guid'][:8]} ({speaker}): OK")

        except Exception as e:
            issues.append(f"  PHRASE {i+1} ({phrase['guid'][:8]}): ERROR: {e}")
            print(f"  [{i+1}/{total}] ERROR: {e}")

    # Write back
    with open(YAML_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)

    print(f"\n=== SUMMARY ===")
    print(f"Total phrases: {total}")
    print(f"Processed: {processed}")
    print(f"Skipped (already filled): {skipped}")
    if issues:
        print(f"Issues ({len(issues)}):")
        for iss in issues:
            print(iss)
    else:
        print("Issues: none")
    print("Done!")


if __name__ == '__main__':
    main()
