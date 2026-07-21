"""Merge voice actor CSV into characters.yaml"""
import csv, yaml, os

CSV = r'C:\Users\Domo\Downloads\table-83d325cb-1583-4896-8871-0843f72b6cb8.csv'
YAML = os.path.join(os.path.dirname(__file__), '..', '..', 'catalog', 'characters.yaml')

NAME_MAP = {
    'Abelard Werserian': 'Абеляр Версериан',
    'Cassia Orsellio': 'Кассия Орселлио',
    'Heinrix van Calox': 'Хайнрикс ван Калокс',
    'Idira Tlass': 'Идира Тласс',
    'Pasqal Haneumann': 'Паскаль Ханеуманн',
    'Sister Argenta': 'Сестра Арджента',
    'Jae Heydari': 'Джаэ Хейдари',
    'Yrliet Lanaevyss': 'Йрлиет Ланаэвисс',
    'Ulfar': 'Ульфар Громолёт',
    'Marazhai Aezyrraesh': 'Маражай Аэзирраэш',
    'Kibellah (DLC)': 'Кибелла',
    'Solomorne Anthar (DLC)': 'Соломон Антар',
    'Eogunn (DLC)': 'Эоганн',
    'Trazyn the Infinite (DLC)': 'Тразин',
    'Theodora von Valancius': 'Теодора фон Валанциус',
    'Kunrad Voigtvir': 'Кунрад Войгтвир',
    'Edelthrad von Valancius': 'Эдельтрад',
}

# Read CSV
actors_by_key = {}
new_chars = {}

with open(CSV, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=',')
    for row in reader:
        en_name = row['Персонаж'].strip()
        actor = {
            'name': row['Рекомендуемый диктор (ФИО)'].strip(),
            'reason': row['Почему подходит'].strip(),
            'demo': row['Где послушать демо'].strip(),
        }
        ru_key = NAME_MAP.get(en_name)
        if ru_key:
            actors_by_key[ru_key] = actor
        else:
            gender = 'M' if row['Пол'].strip() == '♂' else 'F'
            new_chars[en_name] = {
                'name': en_name,
                'gender': gender,
                'role': row['Архетип'].strip(),
                'age': '',
                'personality': '',
                'voice': '',
                'qwen3_voice': '',
                'sound_keys': [],
                'total_phrases': 0,
                'voice_actor': actor,
            }

# Read YAML
with open(YAML, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Apply actors to existing
for ru_key, char_data in data['characters'].items():
    if ru_key in actors_by_key:
        char_data['voice_actor'] = actors_by_key[ru_key]

# Add new characters
for en_name, char_data in new_chars.items():
    data['characters'][en_name] = char_data

data['total_characters'] = len(data['characters'])

# Write
with open(YAML, 'w', encoding='utf-8') as f:
    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

print(f'Updated: {data["total_characters"]} characters total')
matched = len(actors_by_key)
added = len(new_chars)
print(f'Matched existing: {matched}, Added new: {added}')
