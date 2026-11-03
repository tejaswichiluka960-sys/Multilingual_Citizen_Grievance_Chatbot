# Multilingual complaint data plan

## Generated fields

Each row contains:

- `text`: original citizen complaint
- `lang`: `en`, `hi`, `te`, `hinglish` or `tenglish`
- `department`: department code
- `intent`: complaint intent
- `priority`: `low`, `medium` or `high`

## Local generation

The fallback generator works without an API key:

```text
python ml/generate_data.py --rows-per-language 8 --seed 42
```

It writes `raw.csv`, `train.csv`, `test.csv` and `handwritten_test.csv` under `ml/data/`. Generated files are ignored by Git so the corpus can be regenerated from source.

## Public data ideas

The final project may reference AI4Bharat resources such as Samanantar, IN22 and IndicXNLI, public grievance category taxonomies and relevant Hugging Face model cards. Before adding any external text, verify its license, avoid personal information and record attribution in the final README.
