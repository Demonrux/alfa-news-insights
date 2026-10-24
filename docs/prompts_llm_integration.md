# Встраивание PE и агента в репозиторий

Файлы из архива ложатся в существующие зоны: `prompts/` (Prompt Engineering) и `llm/agent/`, `llm/models.yaml` (ML/LLM).
Новых папок в корне нет. Если в `prompts/` и `llm/` лежат заглушки (`.gitkeep`, `README.md`), их можно заменить.
Не заменяйте файлы, которые уже написала Анель в `llm/`: архив добавляет только `llm/agent/` и `llm/models.yaml`.

## pyproject.toml

Добавить зависимости и настройки тестов (если секции уже есть — дописать строки):

```toml
[project]
dependencies = [
  "jinja2>=3.1",
  "jsonschema>=4.20",
  "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.setuptools.packages.find]
include = ["prompts*", "llm*", "backend*"]

[tool.pytest.ini_options]
testpaths = ["prompts/pe/tests", "llm/agent/tests"]
pythonpath = ["."]
```

## .env.example

```
LLM_API_BASE=https://<эндпоинт организаторов>/v1
LLM_API_KEY=
LLM_TIMEOUT=90
PE_TRACE_DIR=runs/traces
# необязательно, если код лежит не в корне репозитория
# PE_PROMPTS_DIR=/app/prompts
# PE_MODELS_FILE=/app/llm/models.yaml
# PE_RUNS_DIR=/app/runs
```

## .gitignore

```
runs/
examples/
```

## docker-compose.yml

Контейнеру backend нужны папки `prompts/` и `llm/` и корень репозитория в `PYTHONPATH`:

```yaml
  backend:
    volumes:
      - ./prompts:/app/prompts:ro
      - ./llm:/app/llm:ro
      - ./runs:/app/runs
    environment:
      PYTHONPATH: /app
      PE_TRACE_DIR: /app/runs/traces
    env_file: .env
```

Если backend собирается через `COPY` в Dockerfile, вместо volumes скопируйте `prompts/` и `llm/` в `/app`.

## Вызов из backend

```python
from llm.agent import InsightRejected, NotRelevant, PipelineError, Trace, run_insight_pipeline
from prompts.pe.domain.model import NotEligible
from prompts.pe.infra.llm import BudgetExceeded
```

Эндпоинт пишется через `def`, а не `async def`: пайплайн синхронный, FastAPI выполнит его в отдельном потоке.
Полный пример эндпоинта и формат входа — в `prompts/README.md`, раздел «Интеграция с FastAPI».
Реальная ручка добавлена в `backend/app/api.py`: `POST /cards` вызывает `run_insight_pipeline`; запуск API из корня репозитория —
`uvicorn backend.app.api:app --reload`. Для live-вызовов клиент читает `LLM_API_KEY` и `LLM_API_BASE` (поддерживается и старое имя `LLM_BASE_URL`).
Если тарифы не заданы в `llm/models.yaml`, локальный журнал сохраняет токены, но не считает расход; общий лимит и сброс в 03:00 МСК
контролирует API организаторов.

## Проверка после копирования

```bash
pip install -e ".[dev]"
python -m pytest -q
python -m prompts.pe theses verify
python -m llm.agent prompts/cases/p5_cases.yaml --case rate_cfo_construction
```
