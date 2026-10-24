import re
import sys

DISCLAIMER_MARKERS = (
    "все права защищены",
    "исключительной собственностью",
    "несанкционированное копирование",
    "распространение настоящего материала",
    "в отсутствие разрешения",
    "данный материал",
    "не является деятельностью по инвестиционному",
    "индивидуальной инвестиционной",
    "инвестиционной рекомендацией",
    "маркет-мейкер",
    "ценные бумаги",
    "валютный риск",
    "финансовыми консультантами",
    "законов, действующих",
    "законом, лица",
    "соблюдать их",
    "альфа групп",
    "конфликт интересов",
    "контакты и дисклеймер",
    "приобретением",
    "заверений",
    "руководящие",
    "консультантов, брокеров",
    "предупреждения",
)

LETTERS = re.compile(r"[А-Яа-яЁёA-Za-z]")
LONG_WORD = re.compile(r"[А-Яа-яЁё]{5,}")

OCR_FIXES = {
    "py6.": "руб.",
    " Toro": " того",
    " rir": " г/г",
    " r/r": " г/г",
    " 2/2": " г/г",
    " 6.п.": " б.п.",
    " 6.n.": " б.п.",
}


def fix_ocr(line: str) -> str:
    """Исправляет частые ошибки распознавания текста"""
    for wrong, right in OCR_FIXES.items():
        line = line.replace(wrong, right)
    return line


def is_noise(line: str) -> bool:
    """Проверяет, что строка мусор от распознавания"""
    s = line.strip()
    if not s:
        return True
    if s.startswith("=== page"):
        return False
    low = s.lower()
    if any(m in low for m in DISCLAIMER_MARKERS):
        return True
    letters = len(LETTERS.findall(s))
    if len(s) < 25 and letters < len(s) * 0.7:
        return True
    if len(s) < 6:
        return True
    return letters < len(s) / 3 and not LONG_WORD.search(s)


def clean(text: str) -> str:
    """Очищает распознанный текст отчёта"""
    out = [fix_ocr(line.rstrip()) for line in text.splitlines() if not is_noise(line)]
    return "\n".join(out) + "\n"


def main(src: str, dst: str) -> None:
    """Очищает файл отчёта и сохраняет результат"""
    with open(src, encoding="utf-8") as f:
        data = f.read()
    with open(dst, "w", encoding="utf-8") as f:
        f.write(clean(data))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
