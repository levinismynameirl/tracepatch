# Data Science & Pipeline Tracing

This guide covers using `tracepatch` in data-science and ML workflows.  The
library is deliberately **zero-dependency** — it will never pull in pandas,
numpy, or scikit-learn.  Instead, it instruments *your* code while letting you
surgically exclude library internals that would flood the trace.

---

## Quick Start

```python
from tracepatch import trace

with trace(ignore_modules=["pandas", "numpy", "sklearn"], label="train-pipeline") as t:
    df = load_data("train.csv")
    X, y = preprocess(df)
    model.fit(X, y)

print(t.tree())
```

The `ignore_modules` list tells tracepatch to skip calls *inside* those
packages.  Your functions (`load_data`, `preprocess`) still appear in the
trace, but the thousands of internal numpy/pandas calls do not.

---

## Recommended `ignore_modules` by Framework

| Framework | Suggested ignores |
|-----------|-------------------|
| pandas + numpy | `["pandas", "numpy"]` |
| scikit-learn | `["sklearn", "numpy", "scipy"]` |
| PyTorch | `["torch", "numpy"]` |
| TensorFlow / Keras | `["tensorflow", "keras", "numpy"]` |
| Hugging Face Transformers | `["transformers", "torch", "numpy", "tokenizers"]` |

You can also set these in `tracepatch.toml`:

```toml
ignore_modules = ["pandas", "numpy", "sklearn", "scipy"]
```

---

## Setting Sensible Limits

Data pipelines can generate millions of function calls.  Always set `max_calls`
and `max_time` to avoid runaway traces:

```python
with trace(max_calls=5000, max_time=10.0, ignore_modules=["pandas"]) as t:
    pipeline.run(data)
```

If the trace is cut short you can check:

```python
print(t.was_limited)  # True if a limit was hit
print(t.summary())    # Shows stats even when limited
```

---

## Using `include_modules` for Precision

Instead of excluding libraries, you can **include only** your own code:

```python
with trace(include_modules=["myapp"]) as t:
    myapp.train(df)
```

Only functions in modules whose name starts with `myapp` will be traced.
Everything else is silently ignored.

---

## Pipeline Step Tracing

For multi-stage pipelines, use `Pipeline` to get per-step timing:

```python
from tracepatch import Pipeline

with Pipeline(label="sklearn-training") as pipe:
    with pipe.step("load"):
        df = load_data("train.csv")
    with pipe.step("preprocess"):
        X, y = preprocess(df)
    with pipe.step("train"):
        model.fit(X, y)

pipe.summary()
```

This prints:

```
Step         Calls  Duration  % of Total
──────────────────────────────────────────
load           142    1.23s     31.2%
preprocess     891    2.04s     51.8%
train           23    0.67s     17.0%
```

`Pipeline` forwards all `trace()` options:

```python
with Pipeline(label="etl", ignore_modules=["pandas"], max_calls=10000) as pipe:
    ...
```

---

## Memory Tracking (Opt-In)

For profiling memory-heavy pipelines, enable `track_memory`:

```python
with trace(track_memory=True, ignore_modules=["pandas"]) as t:
    big_df = load_huge_csv("data.csv")
    processed = transform(big_df)

print(t.tree())
```

Memory deltas appear next to each call:

```
load_huge_csv(...)  [1.2s, +128.4 MB]
  └─ transform(...)  [0.8s, +64.2 MB]
```

> **Warning:** Memory tracking uses `tracemalloc` which adds real overhead.
> Never use it in production.  It is explicitly opt-in and off by default.

---

## Statistical Profiling Mode

When you need a lighter-weight overview without capturing every call:

```python
with trace(sample=0.1, ignore_modules=["pandas"]) as t:
    pipeline.run(large_dataset)

print(t.tree())
```

With `sample=0.1`, approximately 10% of function calls are recorded.
This uses `sys.setprofile` (call/return hooks, lower overhead than the
default `sys.settrace` mechanism) and produces approximate timing without
the full call tree.

This is the bridge between "scalpel debugging" and "profiling" — useful
for large-scale pipelines where full tracing is too expensive.

---

## Jupyter Notebooks

tracepatch integrates with Jupyter via `t.show()`:

```python
from tracepatch import trace

with trace(ignore_modules=["pandas", "numpy"]) as t:
    result = my_pipeline(df)

t.show()  # Interactive HTML tree inline in the notebook
```

Or use the cell magic:

```python
%load_ext tracepatch

%%tracepatch --label "experiment-1" --max-calls 5000
result = preprocess(df)
model.fit(result)
```

Install the notebook extra for IPython support:

```
pip install tracepatch[notebook]
```

---

## Tips

1. **Start narrow.** Use `include_modules=["mypackage"]` first, then widen.
2. **Set `max_calls` aggressively.** 5 000 calls is usually enough to find the
   bottleneck in a pipeline.
3. **Use labels.** `label="load"`, `label="train"` — they appear in JSON
   exports and flamegraphs.
4. **Export flamegraphs** for visual analysis: `t.to_flamegraph("profile.svg")`.
5. **Check `t.explain()`** for an automatic narrative about the trace.
