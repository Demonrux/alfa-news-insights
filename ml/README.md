# ML retrieval module

The module provides a reusable multilingual semantic retrieval stage:

1. `BGEEmbedder` embeds a query and news/company text with `BAAI/bge-m3`.
2. `NewsRetriever` selects a dense-similarity shortlist.
3. `BGEReranker` reorders that shortlist with `BAAI/bge-reranker-v2-m3`.

Install the optional dependency from the repository root:

```powershell
python -m pip install -e ".[ml]"
```

The first search downloads model weights from Hugging Face. Importing `ml` does
not load weights. By default the models run on the device selected by
Sentence Transformers; override it with `ML_DEVICE=cpu` or a supported device
such as `cuda`.

```python
from ml import Candidate, NewsRetriever

items = [
    Candidate("news-1", "ЦБ повысил ключевую ставку до 18 процентов"),
    Candidate("news-2", "Компания заключила контракт на строительство завода"),
]
results = NewsRetriever().search(
    "Изменение ключевой ставки и влияние на заёмщиков",
    items,
    top_k=5,
    rerank_k=20,
)
for result in results:
    print(result.candidate.id, result.score, result.dense_score)
```

Pass the searchable corpus as `Candidate` objects. `metadata` is preserved with
each result, so callers can carry database IDs, publication dates, source, or
company identifiers through retrieval. This module does not fetch database
rows or persist vectors; the backend can connect its repositories and choose a
vector index when the corpus size requires one.

Optional settings:

| Variable | Default |
| --- | --- |
| `ML_EMBEDDING_MODEL` | `BAAI/bge-m3` |
| `ML_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` |
| `ML_DEVICE` | automatic |
