# Prompt Engineering — «Новостная аналитика для бизнес-решений»

Зона Насти (ML/LLM/Prompt Engineer): всё, что говорит модель, и проверка того, что она не врёт. Схемы, таксономия,
реестр тезисов ЦМИ, профиль чувствительности, промпты P1–P14, автопроверка, критик, агентный цикл, метрики, тесты.

```bash
pip install -e ".[dev]"                                  # зависимости из pyproject.toml в корне
python -m pytest -q prompts/pe/tests llm/agent/tests     # 97 тестов, без API
python -m prompts.pe theses verify                       # 56 цитат реестра найдены в текстах отчётов
```

## Где что лежит в репозитории

Слои, зависимости только сверху вниз: `llm/agent → prompts/pe/app → prompts/pe/infra → prompts/pe/domain`. Домен не читает
файлы и не ходит в сеть, справочники получает объектом `Refs`.

```
prompts/                      зона Prompt Engineering
  p*.md, style_guide.md       промпты и стиль
  schemas/                    JSON-схемы ответов (контракт с backend и frontend)
  templates/                  шаблоны: портрет, контрагенты, Zero Trust
  *.yaml, *.csv               таксономия, признаки, действия, дисклеймеры, реестр тезисов ЦМИ
  cases/                      тест-кейсы промптов (yaml)
  reports_text/               тексты отчётов ЦМИ после OCR
  scripts/                    OCR отчётов, запускается один раз
  pe/                         код
    domain/                   правила без ввода-вывода: model, text, company, dataset, checks, metrics
    infra/                    repo (чтение prompts), llm (вызов моделей, журнал, лимит, разбор JSON)
    app/                      context, feed, theses, mocks, evals
    cli.py                    python -m prompts.pe …
    tests/                    тесты кода PE
llm/                          зона ML/LLM Engineer
  models.yaml                 модель для каждой задачи, запасные модели, цены
  agent/                      агентный пайплайн для backend
    errors.py, ask.py, tools.py, planner.py, loop.py, trace.py, demo.py
    tests/                    тесты пайплайна
```

## Команды

```bash
python -m prompts.pe run p5_interpret prompts/cases/p5_cases.yaml --mode dry       # рендер и токены, бюджет не тратится
python -m prompts.pe run p5_interpret prompts/cases/p5_cases.yaml --mode mock      # вся цепочка без API
python -m prompts.pe run p5_interpret prompts/cases/p5_cases.yaml --mode live --limit 2
python -m prompts.pe run p7_critic prompts/cases/p5_cases.yaml --mode live --draft bad
python -m prompts.pe run p12_chat prompts/cases/p5_cases.yaml --mode live --turn 2
python -m prompts.pe render p5_interpret prompts/cases/p5_cases.yaml --case rate_cfo_construction
python -m llm.agent prompts/cases/p5_cases.yaml --case rate_cfo_construction --mode mock --trace-dir runs/traces
python -m prompts.pe theses verify | list --factor KEY_RATE | extract R_STRAT
python -m prompts.pe profile df_Uid_data_hack.csv <SYNTHETIC_U>
python -m prompts.pe examples --out examples/
python -m prompts.pe metrics p1 "runs/p1_classify_live_*.jsonl"
python -m prompts.pe metrics judge "runs/p13_judge_live_*.jsonl"
python -m prompts.pe metrics agreement "runs/p13_judge_live_*.jsonl" human_scores.csv
python -m prompts.pe metrics grounding "runs/p5_interpret_live_*.jsonl"
python -m prompts.pe metrics ranking golden_set.csv ranking.csv --k 5
```

Живые прогоны: `LLM_API_BASE`, `LLM_API_KEY` (если `LLM_API_BASE` не задан, используется адрес API организаторов). Модели по задачам,
запасные модели и цены — `llm/models.yaml`. В журнал пишутся модель, версия промпта, токены и стоимость. Цены вводятся в рублях за 1 000 токенов
для каждой модели. Пока тарифы организаторов не опубликованы, локальный журнал не может проверять расход в рублях; лимит общего ключа 500 ₽/день
контролирует API организаторов. Ответ `Budget has been exceeded` преобразуется в `BudgetExceeded` без вызова резервной модели.

Форматы файлов для метрик: `golden_set.csv` — `company_id,event_id,relevance` (0 / 1 / 2, где 2 — эталонная новость);
`ranking.csv` — `company_id,event_id,rank`; `human_scores.csv` — `case,q1_what_happened,…,q6_grounding`.

## Пути при встраивании в репозиторий

По умолчанию всё ищется рядом с папкой `pe/`. Если Back положит код в другое место, пути задаются переменными окружения:
`PE_PROMPTS_DIR` (папка prompts), `PE_REPORTS_DIR` (тексты отчётов ЦМИ), `PE_MODELS_FILE` (файл моделей, в том числе
`llm/models.yaml` Анель), `PE_RUNS_DIR` (журнал вызовов и отчёты прогонов), `PE_TRACE_DIR` (трейсы агента).

## Интеграция с FastAPI

Рабочее приложение уже находится в `backend/app/api.py`. Запуск из корня репозитория:

```bash
uvicorn backend.app.api:app --reload
```

Документация API будет доступна по адресу `http://127.0.0.1:8000/docs`. `POST /cards` принимает `company_data`, `news_item`, а также необязательные
`role` и `user_title`; формат запроса соответствует примеру ниже.

```python
from fastapi import FastAPI, HTTPException
from llm.agent import InsightRejected, NotRelevant, PipelineError, Trace, run_insight_pipeline
from prompts.pe.domain.model import NotEligible
from prompts.pe.infra.llm import BudgetExceeded

app, P1_CACHE = FastAPI(), {}

@app.post("/cards")
def create_card(body: dict):
    trace = Trace()
    try:
        card = run_insight_pipeline(body["company_data"], body["news_item"], role=body.get("role"),
                                    user_title=body.get("user_title"), trace=trace, cache=P1_CACHE)
    except NotEligible as e:
        raise HTTPException(403, str(e))
    except NotRelevant as e:
        return {"card": None, "reason": str(e), "trace_id": trace.run_id}
    except BudgetExceeded as e:
        raise HTTPException(429, str(e))
    except (InsightRejected, PipelineError) as e:
        raise HTTPException(422, {"reason": str(e), "trace_id": trace.run_id})
    return {"card": card, "trace_id": trace.run_id, "trace": trace.summary()}
```

Вход `run_insight_pipeline`: `company_data` — `{"company": строка df_Uid_data_hack.csv, "group", "counterparties",
"components", "role", "user_title"}` или сама строка CSV; `news_item` — `{"id", "title", "text", "source", "url", "published_at"}`.
Дополнительно: `role`, `user_title`, `today`, `caller`, `tools`, `trace`, `cache` (кэш P1 в памяти процесса), `event` (готовый P1
из базы, если новости классифицирует отдельный воркер). Строка «почему вы видите» для ленты до генерации карточки —
`pe.app.feed.why_line(components)`. В трейсе на шаге F — `grounded_share` и `personalized_share` для экрана жюри.

Шаги пайплайна: **А** P1 — событие и факторы (один раз на новость, `cache`), детектор инъекций → флаг `injection_suspected`;
**Б** релевантность (профиль чувствительности × факторы, контрагенты из затронутых отраслей), P4 — план, инструменты
`get_profile` и `search_alfa_research` обязательны; **В** P5; **Г** автопроверка → P7 → P8, не больше двух исправлений;
**F** `finalize_card` ставит роль, `badge` и `disclaimer`, `api_errors` проверяет insight.json и бейдж. Остались блокирующие
ошибки — `InsightRejected`, карточка клиенту не уходит; замечания уровня major не блокируют выдачу и видны в трейсе.

Zero Trust: новости, отчёты, внешние данные и вопрос в чате приходят в тегах `<untrusted_news>`, `<untrusted_report>`,
`<untrusted_external>`, `<untrusted_question>`; служебные теги и маркеры внутри ломаются; правило — `prompts/templates/zero_trust.j2`,
подключено во все промпты. Четыре блока карточки: Факт `what_happened`, Позиция банка `bank_view` (только тезисы
`thesis_registry.csv`), Вывод AI `ai_conclusions`/`impact`/`risks`/`opportunities`/`scenarios`, Гипотеза `hypotheses`.
Без тезисов ЦМИ — `source_basis = external_only`, `badge = "Не является позицией банка"` и соответствующий дисклеймер.

## Стыки с командой

| Кому | Что | Где |
|---|---|---|
| Front, Back | JSON-схемы и примеры карточек с текстами для интерфейса (`ui`: дисклеймер, пояснение, `not_bank_position`) | `prompts/schemas/`, `python -m prompts.pe examples` |
| Back | Очистка CSV: `clean_companies`, `summarize_groups`, `counterparties_from_payments`; генерация: `run_insight_pipeline` | `prompts/pe/domain/dataset.py`, `llm/agent/` |
| Анель | `run_insight_pipeline(..., tools={...})`: свои `search_news` и `search_alfa_research` (RAG) подменяют локальные; кэш P1 `cache={}` | `llm/agent/planner.py`, `prompts/schemas/plan.json` |
| Анель (RAG) | Тексты отчётов, реестр тезисов с факторами | `prompts/reports_text/`, `prompts/thesis_registry.csv` |
| Product | Реестр тезисов, правила действий, ручная оценка для сверки судьи | `thesis_registry.csv`, `next_actions.yaml`, `metrics agreement` |

Формат `case` для `build_context` и `run_case` — в `prompts/cases/p5_cases.yaml`: `event` (выход P1), `articles`,
`company` (строка CSV), `group`, `counterparties`, `components` (слагаемые скора), опционально `theses`, `chunks`, `external`.

## Роли пользователей

Сервис для людей, а не для юрлиц: у одной компании несколько пользователей с разными ролями. Роль задаётся для пары
«физлицо × компания», карточки кэшируются по ключу (новость, компания, роль). Семь ролей целевой аудитории кейса —
`prompts/p6_roles.md`: `owner` собственник, `ceo` генеральный директор, `cfo` финансовый директор, `treasurer`
руководитель казначейства, `chief_accountant` главный бухгалтер, `c_level` другой руководитель уровня C, `other` сотрудник,
влияющий на решения. Должность из профиля (`user_title` в кейсе) дописывается к блоку роли — так `c_level` и `other`
получают конкретику. `other` продукты банка не предлагаются. Названия для экрана выбора — `role_names()` и `examples/roles.json`.

В данных кейса роли пользователя нет: её выбирает сам пользователь при первом входе.

## Правила данных (Q&A 20–21.10)

- Только `CL_TYPE = Client`; Prospect и Close Client — `NotEligible`.
- Выручка — за 2025 г. в рублях; 1000, 0 и пусто — заглушки. Крупный бизнес — группа > 15 млрд руб.
- Дубли `SYNTHETIC_U` убираются; ID на ≥ 12 пустых строках — артефакт обезличивания.
- Переводы самой себе (≈ 82 % объёма платежей) — не контрагенты; контрагент вне датасета — «нет информации об отрасли».
- Связи между компаниями по косвенным признакам — только в `hypotheses` с уверенностью и способом проверки.
- `source_basis = external_only` → метка «не позиция банка»; дисклеймер — фиксированный текст интерфейса.

## Находки по материалам

1. PDF отчётов ЦМИ — сканы без текста; тексты распознаны (`scripts/ocr_reports.sh`) и лежат в `prompts/reports_text/`.
2. Файл «Commodities performance» — обзор сталелитейщиков от 15.04.2021: отчёт `stale`, тезисы в карточки не попадают.
3. Прогнозы ЦМИ менялись: ставка на конец 2026 г. 13,5 % → 14,0 %; T-CONS-06 и T-STR-11 — `superseded` (заменены T-RATE-02).

## Принципы кода

- DRY: общие куски вынесены в одно место — `to_json`, `primary_factor`, `event_factors`, `MACRO_FACTORS`, `is_large_business`,
  `render_portrait`, `review_vars`, `gather`, `checks.tag`, `checks.with_severity`, `Prompt.schema_name`; тестовые данные — `tests/data.py`.
  Проверка: `pylint --enable=duplicate-code --min-similarity-lines=3` — повторов нет.
- KISS: длинные цепочки if заменены таблицами (`MOCKS`, `CHECKS`, `METRICS`), большие функции разбиты на шаги;
  `radon cc` — нет функций сложнее уровня C.
- YAGNI: убрано то, что не нужно ни внутри комплекта, ни при встраивании — параметры `max_fix`, `override`, `json_mode`, `retries`,
  поле `url` у статьи, хеш промпта в прогонах, обрезка `materials[-6:]`. Оставлено то, что нужно бэкенду: `event`,
  `why_line`, `grounding`, переменные путей, функции очистки CSV; всё закреплено тестами.
- SOLID: у каждого модуля одна задача (evals разделён на theses, mocks, evals и feed; агент — на errors, ask, tools,
  planner, loop); новые проверки, заглушки, метрики и инструменты добавляются строкой в `INSIGHT_CHECKS`, `MOCKS`, `CHECKS`,
  `METRICS`, `LOCAL_TOOLS` без правки остального кода; встроенные и внешние инструменты имеют одну сигнатуру `(args, case)`
  и взаимозаменяемы; пайплайн зависит от абстракций `Caller` и `Tool`, а не от конкретной модели.
- Без преждевременной оптимизации: один кэш — справочники `refs()` читаются один раз на процесс; убраны отдельные кэши
  ролей и стиля. Кэш P1 оставлен, потому что он требование бюджета, а не оптимизация ради скорости.
- Слои не перепутаны: `domain` ничего не читает с диска, `pe` не знает про `llm/agent`.

## Не определено

- Цены моделей у организаторов: пока `prices: {}` — стоимость в журнале пустая и лимит не срабатывает.
- Точные идентификаторы моделей в API организаторов.
- Показывать ли карточку с замечаниями уровня major после двух исправлений — сейчас показываем (наше решение), блокируют только blocker.
- Таксономия в задаче названа taxonomy.md; источник правды в комплекте — `prompts/taxonomy.yaml`, в P1 он попадает через `taxonomy_block()`.
- Придут ли новые отчёты ЦМИ (~10) и замена отчёта по стали — тогда `python -m prompts.pe theses extract` и ручная сверка.
