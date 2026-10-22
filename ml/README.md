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

## Relevance benchmark

`golden_news_company.csv` contains 48 pairs built from the local
`data/news.json` snapshot and six synthetic demo company profiles. It embeds
the article text, company sector, binary relevance label, taxonomy category,
and a rationale for each label. The project user reviewed the labels on
2026-10-23; rows are marked `reviewed_by_user`. These are still subjective
manual labels, not domain-expert ground truth. Regenerate it after updating the
local snapshot with:

```powershell
python -m ml.build_golden_set
```

Evaluate the dependency-free lexical baseline immediately:

```powershell
python -m ml.evaluate_retrieval --method lexical --out ml/results/lexical.json
```

After installing the optional ML dependencies and downloading model weights,
compare the embedding model and reranker:

```powershell
python -m ml.evaluate_retrieval --method all --out ml/results/models.json
```

The evaluator also accepts `--embedding-model` and `--reranker-model` for
cached or alternative checkpoints, `--hf-home` to select a cache location,
and `--offline` to prohibit hub access.

The report includes macro `Recall@1/3/5`, `MRR`, and per-company scores.

## Initial measurement (2026-10-22)

| Method | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Lexical overlap baseline | 0.1250 | 0.3750 | 0.6250 | 0.7032 |
| Cached `cointegrated/rubert-tiny2` embeddings | 0.0833 | 0.2389 | 0.5639 | 0.5972 |
| BGE-M3 embeddings | 0.1083 | 0.1833 | 0.4444 | 0.6306 |
| BGE-M3 + BGE-reranker-v2-m3 | 0.2056 | 0.5639 | 0.7389 | 0.9167 |
| BGE-M3 + reranker + expanded company context | 0.2056 | 0.5833 | 0.7806 | 0.9167 |

The model comparison is provisional: there are only six company queries and
eight candidate stories per query, and the labels still need domain review.
On this sample, dense retrieval alone is weaker than lexical overlap at
Recall@3/5; adding the cross-encoder reranker improves Recall@3/5 to 0.5639 /
0.7389. Adding hand-written sector terms and synonyms to the company query
then lifts Recall@3/5 further to 0.5833 / 0.7806; MRR and Recall@1 stay flat.
These figures are an initial signal, not a model-selection result.
The scores are saved in `results/lexical.json`, `results/rubert-tiny2.json`,
`results/lexical-expanded-query.json`, `results/bge-m3.json`,
`results/bge-m3-reranker.json`, and
`results/bge-m3-reranker-expanded-query.json`. The RuBERT checkpoint is
Russian-only; BGE-M3 and BGE-reranker-v2-m3 are the multilingual models.

## Recheck (2026-10-23)

Lexical retrieval and BGE-M3 embeddings were rerun on the reviewed 48-pair set;
their metrics matched the initial measurement. The reranker could not be
rechecked because its model weights are not fully available in the local cache
and the Hugging Face Hub download could not be completed. Its table values
above are from the earlier run and remain unconfirmed by this recheck. The
rechecked reports are in `results/lexical-recheck-20261022.json` and
`results/bge-m3-recheck-20261022.json`.
