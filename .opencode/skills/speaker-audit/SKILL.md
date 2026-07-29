---
name: speaker-audit
description: Review one YAML for speaker bugs. Check SELF_ADDR, NARR_MISMATCH, PRL/CH scene-owner bug. Output JSON issues or empty array.
---

# Speaker Audit Skill

Проверка одного YAML-файла на неверные speaker.

## Паттерны для поиска

### SELF_ADDR
Текст обращается к speaker'у по имени/титулу → speaker НЕ тот.
```
"Мастер шепотов, что творится..."  → speaker=Kunrad → SUSPECT
"Леди Теодора, позвольте..."       → speaker=Theodora → SUSPECT
"Экий ты пунктуальный, Кунрад..."  → speaker=Kunrad → SUSPECT
```
**Исключение:** самопредставление — `"Я — Кассия Орселлио"` → VERIFIED

### NARR_MISMATCH
Narrator блок начинается с имени персонажа X, speaker = Y, X ≠ Y:
```
{n}Теодора бросает взгляд на Кунрада.{/n} "Эдельтрад — где он?"
→ narrator про Теодору → speaker = Theodora ≠ Kunrad
```
**Исключение:** narrator описывает действие speaker'а:
```
{n}Кунрад тонко улыбается.{/n} "Разумеется..."
→ narrator про Кунрада, speaker = Kunrad → VERIFIED
```

### PRL/CH scene-owner bug
Событие PRL_ или CH1_/CH2_/CH3_ где speaker = имя_файла (tree owner).
Имя ивента = сцена, не обязательно спикер.
```
event=PRL_KunradUnpleasantNews_24 → speaker=Kunrad (НО текст адресует Кунрада)
```

### Грамматический род
Если спикер женского пола, а глагол мужского рода (или наоборот) — возможно неверно.
```
"заинтригован" (м.р.) → speaker=Theodora (ж.р.) → SUSPECT
```

### Missing override
Есть evidence неверного спикера, но нет `speaker_override` на part.

## Формат вывода

```json
[
  {
    "guid": "полный UUID",
    "speaker": "текущий спикер",
    "suggested": "предполагаемый спикер (или UNKNOWN)",
    "type": "SELF_ADDR | NARR_MISMATCH | PRL_CH | GENDER | MISSING_OVERRIDE",
    "reason": "почему"
  }
]
```

Если всё чисто: `[]`

## Правила

- `speaker` НЕ ТРОГАТЬ — это tree owner
- `speaker_override` ставить ТОЛЬКО на part, не на phrase
- Если не можешь определить кто говорит → suggested = "UNKNOWN"
- Если уже есть `speaker_override` — проверить что он корректный
