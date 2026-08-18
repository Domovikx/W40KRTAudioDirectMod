#!/usr/bin/env python3
"""Environment Descriptions catalog scanner + residual inspector.

Manages catalog/people/Environment_Descriptions.yaml — the catalog of
non-dialog "environment description" texts (interior/object/location
observations shown in-game when inspecting the world).

Source of truth: game localization ruRU.json (GUID -> raw text). These
GUIDs are NOT dialog cues/answers (absent from Sound.json and
blueprints); they are plain localized strings, so the general
generate_catalog.py pipeline does not see them — this tool owns them.

Residual mode (--residual):
    Reads ruRU.json and applies the descriptive filter, but EXCLUDES
    every GUID already living in any catalog/people/*.yaml (including
    Environment_Descriptions.yaml itself and Player_Answers.yaml). The
    result is the "uncategorized remainder" — phrases that have not yet
    been assigned to any character or skip_voiced catalog and that look
    like environment descriptions. Useful for inspecting what could
    still be added without overlap.

Usage:
    python tools/env_scan.py                          # report only (A)
    python tools/env_scan.py --show-b                 # include B in report
    python tools/env_scan.py --json scan.json         # machine-readable
    python tools/env_scan.py --residual               # exclude ALL catalog
                                                       #  GUIDs (incl. env, PA)
    python tools/env_scan.py --residual --json docs/env_residual.json
    python tools/env_scan.py --apply                  # merge category A
    python tools/env_scan.py --apply --categories A,B
    python tools/env_scan.py --apply --include-guid G1,G2
    python tools/env_scan.py --apply --dry-run
    python tools/env_scan.py --residual --rejected-json docs/env_residual_2.json
        # 2nd pass: dump GUIDs REJECTED by the filter with their reasons.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from text_normalize import normalize  # noqa: E402

GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40,000 Rogue Trader"
RU_JSON = Path(GAME) / "WH40KRT_Data" / "StreamingAssets" / "Localization" / "ruRU.json"
SOUND_JSON = Path(GAME) / "WH40KRT_Data" / "StreamingAssets" / "Localization" / "Sound.json"

PEOPLE = ROOT / "catalog" / "people"
ENV_FILE = PEOPLE / "Environment_Descriptions.yaml"

MIN_LEN, MAX_LEN_A, MAX_LEN_B = 40, 300, 800

# Concrete object/inventory nouns (any case) that mark an object-style
# description. Abstract concepts (rumours, fears, decrees...) are excluded —
# they belong to quest journal / codex, not environment descriptions.
OBJECT_START = set("""
стол алтарь дверь двери лифт лифты генератор генераторы окно окна клетка
витрина витрины монумент шип сплав кристалл кристаллы камень камни копия
библиотека статуя статуи когитатор стела зверь конструкция храм артефакт
артефакты предмет панель экран пульт рычаг кнопка шкаф ящик сундук подъёмник
подъемник подиум сцена пентаграмма книга книги пергамент свиток карта карты
глобус телескоп реликварий саркофаг гробница колонна колонны арка мост
лестница трап люк корпус бак трубы кабель провода механизм шестерни реактор
двигатель турбина камин печь купол шпиль башня фонтан сад поле улица площадь
церковь часовня собор зал комната коридор палуба трон кресло стул пюпитр
сейф ваза лампа светильник канделябр подсвечник гобелен ковер портрет
картина бюст скульптура мозаика фреска ящики бочка тележка мусор обломки
череп кости тела труп кровь следы гильзы пятна лужа дым огонь пламя искры
туман пыль грязь слизь паутина трещины щель пролом проход туннель тоннель
шахта пещера грот склеп катакомбы крипта убежище лагерь стоянка доки ангар
цех кузница лаборатория арсенал склад кладовая каюта мостик рубка оружейная
покои спальня кухня столовая трапезная капелла двор плац казарма баррикада
стена стены пол потолок свод балка опора фундамент пандус рельсы пути вагон
цистерна контейнер мешки тюки канаты цепи оковы кандалы колья ловушки силки
перегородка ширма занавес драпировка балдахин кафедра тумба этажерка бюро
комод секретер консоль постамент пьедестал обелиск мемориал мавзолей
усыпальница ниша альков проём проем вход выход тупик ответвление развилка
поворот перекрёсток перекресток переход шлюз отсек трюм туалет душевая баня
сауна бассейн теплица оранжерея стойло конюшня вольер аквариум террариум
клеть скважина рудник прииск карьер штольня штрек забой выработка пласт
жила руда порода скала утёс утес обрыв кряж хребет пик вершина вулкан
гейзер кратер пропасть ущелье каньон овраг лощина долина равнина степь
пустошь болото трясина топь озеро пруд река речка ручей родник источник
водопад пороги мель завод фабрика комбинат мануфактура мастерская студия
гараж депо паркинг аллея бульвар проспект магистраль шоссе дорога тропа
тропинка мостик настил помост эшафот плаха виселица дыба застенок темница
каземат тюрьма острог каторга барак штаб комендатура преторий застава форт
цитадель крепость замок дворец резиденция усадьба поместье имение хутор
деревня село посёлок поселок город городище столица колония поселение
форпост аванпост база станция терминал портал врата ворота колоннада
портик атриум перистиль базилика кирха мечеть синагога капище святилище
жертвенник кадило курильница свечи светильники лампады подсвечники венки
цветы гирлянды ленты знамёна знамена штандарты стяги флаги хоругви иконы
образы лики распятие кресты чётки четки молитвенник псалтырь библия писание
скрижали таблички пилоны устои быки подпоры аркбутаны контрфорсы пинакли
сталактиты сталагмиты натёки наплывы лава магма пепел зола угли головешки
сажа копоть гарь чад смрад вонь запах аромат благовоние ладан мирра смола
деготь нефть солярка бензин топливо горючее реагенты кислоты щёлочь
щелочь удобрения яды токсины отходы отбросы нечистоты стоки канализация
коллектор дренаж канава ров траншея окоп блиндаж дзот бункер бомбоубежище
подземелье подвал цоколь полуподвал чердак мансарда антресоли мезонин
галерея балкон лоджия терраса веранда крыльцо крыша кровля конёк конек
свес карниз фронтон тимпан сандрик наличники ставни жалюзи решётки решетки
прутья прутки скобы петли засовы задвижки щеколды защёлки защелки замки
ключи отмычки слепки оттиски дубликаты шаблоны трафареты лекала выкройки
чертежи схемы диаграммы графики таблицы списки реестры каталоги описи
ведомости накладные квитанции расписки ордера приказы указы манифесты
декреты эдикты рескрипты буллы энциклики грамоты дипломы патенты лицензии
концессии договоры контракты соглашения пакты альянсы коалиции гильдии
братства ордена секты культы ереси расколы скрижали следы
""".split())

ADJ_START = set("""
массивный массивная массивные огромный огромная огромные большой большая
большие небольшой небольшая небольшие маленький маленькая маленькие старый
старая старые ветхий ветхая ветхие сломанный сломанная сломанные
разрушенный разрушенная разрушенные разбитый разбитая разбитые сгоревший
сгоревшая обгоревший обгоревшая запертый запертая запертые закрытый закрытая
закрытые открытый открытая открытые тяжелый тяжелая тяжелые тёмный тёмная
тёмные темный темная темные светлый светлая светлые холодный холодная
холодные горячий горячая горячие влажный влажная влажные сырой сырая сырые
пустой пустая пустые пустынный пустынная упавший упавшая упавшие рухнувший
рухнувшая рухнувшие лежащий лежащая лежащие висящий висящая висящие стоящий
стоящая стоящие застывший застывшая застывшие покрытый покрытая покрытые
заросший заросшая заросшие заваленный заваленная заваленные забитый забитая
забитые почерневший почерневшая почерневшие ржавый ржавая ржавые изогнутый
изогнутая изогнутые искривленный искривленная искривленные резной резная
резные кованый кованая кованые позолоченный позолоченная позолоченные
мраморный мраморная мраморные каменный каменная каменные деревянный
деревянная деревянные металлический металлическая металлические стеклянный
стеклянная стеклянные бетонный бетонная бетонные цементный хромированный
украшенный украшенная украшенные инкрустированный инкрустированная
инкрустированные величественный величественная величественные зловещий
зловещая зловещие жуткий жуткая жуткие странный странная странные необычный
необычная необычные таинственный таинственная таинственные загадочный
загадочная загадочные древний древняя древние античный античная античные
уютный уютная уютные жестокий жестокая ожесточенный ожесточённый кровавый
кровавая кровавые грязный
грязная грязные дымящийся дымящаяся дымящиеся тлеющий тлеющая тлеющие
потрескавшийся потрескавшаяся потрескавшиеся осыпавшийся обветшалый
обветшалая обветшалые неработающий неработающая неработающие выключенный
выключенная работающий работающая работающие гудящий гудящая гудящие
жужжащий воющий завывающий мигающий мигающая мигающие мерцающий мерцающая
мерцающие светящийся светящаяся светящиеся переливающийся переливающаяся
переливающиеся чёрный чёрная чёрные черный черная черные белый белая белые
серый серая серые зелёный зелёная зелёные зеленый зеленая зеленые
фиолетовый фиолетовая фиолетовые золотой золотая золотые серебряный
серебряная серебряные медный медная медные бронзовый бронзовая бронзовые
алый алая алые багровый багровая багровые пепельный пепельная пепельные
угольный угольная угольные серо-зелёный серо-зеленый пыльный пыльная
пыльные точный точная точные упавшая название названия авторы титулы полки
корешки эти те самые давние прежние нынешние минувшие былые грядущие
предстоящие ближайшие далёкие дальние близкие соседние смежные прилегающие
окрестные окрестный верхний нижний средний центральный боковой внутренний
наружный внешний задний передний правый левый дальний ближний южный
северный западный восточный северо-западный северо-восточный юго-западный
юго-восточный главный второстепенный вспомогательный служебный технический
инженерный коммунальный промышленный сельскохозяйственный аграрный
производственный складской портовый доковый военный гражданский
административный жилой общественный культурный религиозный духовный
сакральный священный божественный дьявольский демонический проклятый
благословенный освящённый освященный обычный обычная обычные простой
простая простые немудреный немудрёный немудреная лаконичный лаконичная
суровый суровая суровые аскетичный аскетичная роскошный роскошная роскошные
богатый богатая богатые убогий убогая нищенский нищенская ветхий ветхая
взрыв освещённый освещенный лиловый грандиозный плазменные плазменный
светящиеся
""".split())

PREPOSITIONS = {"на", "в", "во", "у", "за", "под", "перед", "над", "из",
                "по", "со", "с", "между", "около", "возле", "рядом", "внутри",
                "среди", "напротив", "позади", "впереди", "слева", "справа",
                "внизу", "наверху", "посреди", "вдоль", "прямо", "чуть"}

SHORT_PREP = {"с", "в", "у", "к", "на", "за", "по", "из", "о", "об"}

JOURNAL_MARKERS = [
    "задание", "квест", "цель обновлена", "вы должны", "вам нужно",
    "вам предстоит", "ваша цель", "отправляйтесь", "вернитесь",
    "поговорите", "найдите", "принесите", "обыщите", "уничтожьте",
    "защитите", "доберитесь", "пройдите", "приготовьтесь", "внимание",
    "новое задание", "журнал", "награда", "вознаграждение", "прибыль",
    "награждён", "награжден",
]

ENCYCLOPEDIA_MARKERS = [
    "известен как", "известный как", "также известный как", "известная как",
    "является", "представляет собой", "выступает", "выступающий",
    "находящийся на вооружении", "называют", "называемый", "называется",
    "некогда", "раса", "организация", "понятие", "термин", "титул",
    "звание", "фракция", "институт", "учреждение", "подразделение",
    "империум", "псайкер", "варп", "хаос", "планета", "галактик",
    "золотой трон", "император", "астрономикон", "механикус",
    "уменьшен на", "увеличивает", "даёт +", "дает +", "бонус", "урон",
    "единица", "способность", "навык", "умение", "профессия", "должность",
    "сан", "чин", "ранг", "ген", "мутант", "киборг", "аугмент",
    "скорость", "радиус", "дальность", "перезарядк", "стоимость", "цена",
    "ресурс", "запас", "броня", "сопротивление", "непроницаемость",
    "устойчивость", "иммунитет", "эффект", "статус", "условие",
]

QUOTE_CHARS = ('"', "«", "»", "„", "“", "”")


def load_json_strs(path: Path) -> dict[str, str]:
    """GUID -> raw Text from a localization json."""
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    out = {}
    for k, v in data.get("strings", {}).items():
        if isinstance(v, dict):
            out[k] = v.get("Text", "")
        else:
            out[k] = str(v)
    return out


def load_sound_guids(path: Path) -> set[str]:
    """GUIDs that have a Wwise event (voiced dialog) — never env descriptions."""
    if not path.exists():
        return set()
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    return set(data.get("strings", {}).keys())


def load_catalog_guids(residual: bool = False) -> dict[str, str]:
    """guid -> filename for every phrase in catalog/people/.

    residual=False (default): skip index.yaml + Player_Answers.yaml +
      Environment_Descriptions.yaml — i.e. don't treat these as duplicates
      of env descriptions (so they can still be ADDED to env descriptions).
    residual=True: skip only index.yaml — exclude every GUID that has
      been categorized anywhere (the remaining pool is "uncategorized").
    """
    result = {}
    skip = {"index.yaml"}
    if not residual:
        skip |= {"Player_Answers.yaml", ENV_FILE.name}
    for path in sorted(PEOPLE.glob("*.yaml")):
        if path.name in skip:
            continue
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for ph in data.get("phrases", []):
            g = ph.get("guid", "")
            if g:
                result[g] = path.name
    return result


def has_markup(t: str) -> bool:
    return any(x in t for x in ("{", "}", "<", ">", "[DRAFT]", "\n", "\r"))


def journal_like(t: str) -> bool:
    low = t.lower()
    return any(m in low for m in JOURNAL_MARKERS)


def encyclopedia_like(t: str) -> bool:
    low = t.lower()
    return any(m in low for m in ENCYCLOPEDIA_MARKERS)


_CASE_SUFFIXES = (
    "ого", "его", "ому", "ему", "ыми", "ими", "ой", "ая", "яя", "ое",
    "ее", "ые", "ие", "ах", "ях", "ам", "ям", "ом", "ем", "ой", "а",
    "я", "е", "ы", "и", "у", "ю", "о", "ь",
)


def ru_stem(w: str) -> str:
    w = w.lower().rstrip(",;.:!?")
    if len(w) <= 4:
        return w
    for suf in _CASE_SUFFIXES:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[: -len(suf)]
    return w


_OBJECT_STEMS = {ru_stem(w) for w in OBJECT_START}
_ADJ_STEMS = {ru_stem(w) for w in ADJ_START}
_PREP_STEMS = {ru_stem(w) for w in PREPOSITIONS}

LOCATIVE_STARTS = {"здесь", "тут", "это", "эта", "этот", "там", "напротив"}


def _token_is_object(tok: str) -> bool:
    s = ru_stem(tok)
    return s in _OBJECT_STEMS or s in _ADJ_STEMS


def object_start_ok(words: list[str]) -> tuple[bool, str]:
    if not words:
        return False, "start_not_object"
    first = ru_stem(words[0])
    if first in _OBJECT_STEMS or first in _ADJ_STEMS:
        return True, ""
    if first in _PREP_STEMS and len(words) > 1 and _token_is_object(words[1]):
        return True, ""
    if first in LOCATIVE_STARTS and len(words) > 1:
        for w in words[1:5]:
            if _token_is_object(w):
                return True, ""
    return False, "start_not_object"


def classify(text: str, position: int, sound_guids: set[str],
             guid: str, catalog_guids: dict[str, str]):
    """Return candidate dict (accepted) or str (rejection reason).

    Reasons: already_categorized, voiced_dialog, too_short,
             has_markup, no_period, no_object_token.

    Order matters for diagnostics: catalog/sound checks run first so the
    rejected-bucket tells us truthfully whether every GUID belongs to a
    catalog/people file or to Sound.json before any text heuristics fire.
    """
    if guid in catalog_guids:
        return "already_categorized"
    if guid in sound_guids:
        return "voiced_dialog"
    if not text or len(text) < MIN_LEN:
        return "too_short"
    if has_markup(text):
        return "has_markup"
    if not text.endswith("."):
        return "no_period"
    words = text.split()
    if not any(_token_is_object(w) for w in words[:8]):
        return "no_object_token"
    reasons = []
    cat = "A"
    if len(text) > MAX_LEN_A:
        reasons.append("too_long")
    if any(q in text for q in QUOTE_CHARS):
        reasons.append("quotes")
    if ":" in text:
        reasons.append("colon")
    if journal_like(text):
        reasons.append("journal_like")
    if encyclopedia_like(text):
        reasons.append("encyclopedia")
    ok, reason = object_start_ok(words)
    if not ok:
        reasons.append(reason)
    if reasons:
        cat = "B"
    return {"guid": guid, "pos": position, "cat": cat,
            "reasons": reasons, "text": text}


def scan(ru: dict[str, str], sound_guids: set[str],
         catalog_guids: dict[str, str]) -> list[dict]:
    cands = []
    keys = list(ru.keys())
    for pos, guid in enumerate(keys):
        c = classify(ru[guid], pos, sound_guids, guid, catalog_guids)
        if isinstance(c, dict):
            cands.append(c)
    return cands


def scan_with_rejections(ru: dict[str, str], sound_guids: set[str],
                          catalog_guids: dict[str, str]
                          ) -> tuple[list[dict], list[dict]]:
    """Like scan() but also reports rejected GUIDs with their reason."""
    accepted = []
    rejected = []
    keys = list(ru.keys())
    for pos, guid in enumerate(keys):
        c = classify(ru[guid], pos, sound_guids, guid, catalog_guids)
        if isinstance(c, dict):
            accepted.append(c)
        else:
            rejected.append({"guid": guid, "pos": pos, "reason": c,
                             "text": ru[guid] or ""})
    return accepted, rejected


def make_phrase(guid: str, text: str) -> dict:
    return {"guid": guid, "text": text, "status": "active",
            "reviewed": False,
            "parts": [{"speaker": "narrator", "text_clean": normalize(text)}]}


def write_yaml(path: Path, data: dict) -> bool:
    text = yaml.dump(data, allow_unicode=True, indent=2, sort_keys=False,
                     default_flow_style=False, width=65535)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if text == old:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def rebuild_index() -> None:
    entries = []
    total = 0
    for path in sorted(PEOPLE.glob("*.yaml")):
        if path.name in ("index.yaml", "Player_Answers.yaml"):
            continue
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        n = len(d.get("phrases", []))
        entries.append({"name": d.get("name", path.stem),
                        "doc": d.get("doc", ""), "total_phrases": n})
        total += n
    write_yaml(PEOPLE / "index.yaml", {
        "generated": "merge_speakers rebuild",
        "total_characters": len(entries),
        "total_phrases": total,
        "characters": entries,
    })


def do_apply(cands: list[dict], ru: dict[str, str], categories: set[str],
             include_guids: set[str]) -> dict:
    if not ENV_FILE.exists():
        data = {"name": "Environment Descriptions",
                "description": "Тексты описаний окружения (локации, предметы, интерьер) — не диалоговые реплики",
                "phrases": []}
    else:
        with open(ENV_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    phrases = data.get("phrases", [])
    by_guid = {p["guid"]: p for p in phrases}

    new, updated, missing = [], [], []
    for c in cands:
        g = c["guid"]
        if g in by_guid:
            continue
        if g not in include_guids and c["cat"] not in categories:
            continue
        by_guid[g] = make_phrase(g, c["text"])
        new.append(g)
    for g, ph in by_guid.items():
        src = ru.get(g)
        if src is None:
            if ph.get("status") != "missing_in_game":
                ph["status"] = "missing_in_game"
                missing.append(g)
            continue
        if ph.get("text") != src:
            if ph.get("status") == "missing_in_game":
                ph["status"] = "active"
            ph["text"] = src
            if ph.get("parts"):
                ph["parts"][0]["text_clean"] = normalize(src)
            ph["updated"] = True
            ph["reviewed"] = False
            updated.append(g)

    changed = bool(new or updated or missing)
    if changed:
        data["total_phrases"] = len(by_guid)
        data["phrases"] = list(by_guid.values())
        write_yaml(ENV_FILE, data)
        rebuild_index()
    return {"new": new, "updated": updated, "missing": missing,
            "changed": changed}


def print_report(cands: list[dict], show_b: bool) -> None:
    cats = {"A": [], "B": []}
    for c in cands:
        cats[c["cat"]].append(c)
    print(f"=== env_scan: {len(cands)} candidates "
          f"(A={len(cats['A'])}, B={len(cats['B'])}) ===")
    shown = cats["A"] + (cats["B"] if show_b else [])
    for c in shown:
        tag = "A" if c["cat"] == "A" else "B"
        reason = f" [{', '.join(c['reasons'])}]" if c["reasons"] else ""
        print(f"{tag} {c['pos']:6d} {c['guid']} {reason}\n    {c['text'][:110]}")
    if cats["B"] and not show_b:
        print(f"... ({len(cats['B'])} B-candidates hidden; use --show-b)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="merge candidates into the YAML")
    ap.add_argument("--categories", default="A", help="categories to apply (default A)")
    ap.add_argument("--include-guid", default="", help="comma-separated GUIDs to force-add")
    ap.add_argument("--dry-run", action="store_true", help="apply: preview only")
    ap.add_argument("--json", default="", help="write scan results to a JSON file")
    ap.add_argument("--limit", type=int, default=0, help="report/apply: max candidates")
    ap.add_argument("--show-b", action="store_true", help="also print B-candidates")
    ap.add_argument("--residual", action="store_true",
                    help="exclude every GUID categorized anywhere in "
                    "catalog/people (incl. Environment_Descriptions, "
                    "Player_Answers). Result = uncategorized remainder.")
    ap.add_argument("--rejected-json", default="",
                    help="also dump GUIDs REJECTED by the filter with their "
                    "rejection reason (too_short/has_markup/no_period/"
                    "voiced_dialog/already_categorized/no_object_token)")
    args = ap.parse_args()

    ru = load_json_strs(RU_JSON)
    sound_guids = load_sound_guids(SOUND_JSON)
    catalog_guids = load_catalog_guids(residual=args.residual)
    if args.rejected_json:
        accepted, rejected = scan_with_rejections(ru, sound_guids, catalog_guids)
        cands = accepted
    else:
        cands = scan(ru, sound_guids, catalog_guids)
        rejected = None
    if args.limit:
        cands = cands[:args.limit]

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(cands, f, ensure_ascii=False, indent=1)

    if args.rejected_json:
        with open(args.rejected_json, "w", encoding="utf-8") as f:
            json.dump(rejected, f, ensure_ascii=False, indent=1)
        from collections import Counter
        c = Counter(r["reason"] for r in rejected)
        print(f"=== rejected -> {args.rejected_json}: {len(rejected)} ===")
        for r, n in sorted(c.items(), key=lambda x: -x[1]):
            print(f"  {r}: {n}")

    if not args.apply:
        print_report(cands, args.show_b)
        return

    include = {g.strip() for g in args.include_guid.split(",") if g.strip()}
    cats = {x.strip() for x in args.categories.split(",") if x.strip()}
    if args.dry_run:
        sel = [c for c in cands if c["guid"] in include or c["cat"] in cats]
        print(f"=== dry-run: {len(sel)} would be added (of {len(cands)}) ===")
        for c in sel:
            print(f"{c['cat']} {c['pos']:6d} {c['guid']}\n    {c['text'][:110]}")
        return
    res = do_apply(cands, ru, cats, include)
    print(f"=== apply: new={len(res['new'])} updated={len(res['updated'])} "
          f"missing={len(res['missing'])} changed={res['changed']} ===")
    for g in res["new"]:
        print(f"  NEW   {g}")
    for g in res["updated"]:
        print(f"  UPD   {g}")
    for g in res["missing"]:
        print(f"  MISS  {g}")


if __name__ == "__main__":
    main()
