# Job: document search that survives updates, deletes and a restart

Build a small command-line document search tool that uses **{product} {version}** for storage and
search. Start from the docs: {docs_url}

{setup_note}

## What to build

An executable `/work/docsearch` (any language) with these commands. Each exits 0 on success.

- `docsearch add FILE`: FILE is JSON Lines, one document per line:
  `{"id": "doc-00001", "text": "...", "category": "docs", "vector": [64 numbers]}`.
  A new id is inserted. An id that already exists is replaced: its text, category and vector (so it
  no longer shows up under its old category or near its old vector).
- `docsearch delete ID [ID ...]`: removes those documents. Ids that don't exist are ignored.
- `docsearch query FILE [--k K] [--category C]`: FILE holds one JSON array of 64 numbers. Print the
  ids of the K most similar documents (default 5) by **cosine similarity**, most similar first, one
  id per line and nothing else on stdout (fewer than K only if fewer documents qualify). With
  `--category C`, only documents in category C. An approximate index is fine: at least 4 of the true
  top 5 must come back, and the first result must be one of the true top 2.
- `docsearch count`: print the number of stored documents, as a bare number.

Plus `/work/start.sh` and `/work/stop.sh`: start and stop anything your store needs running (they can
do nothing if nothing needs to run). `start.sh` must work both on a fresh machine with an empty
`/work/data` and on existing data.

Rules:
- All data lives under `/work/data`.
- {product} does the storing and the similarity search. No hand-written index, no JSON file, no
  brute-force search of your own.
- The vectors are given. Don't compute embeddings.

## Sample data

`/work/job/fixtures/` has 20 documents (`docs.jsonl`), three query vectors and the right answers in
`expected.txt`. Use them to test your work.

## How it will be checked

After you stop, a separate check runs your tool on new data (a few hundred documents) in this order:
stop anything running, empty `/work/data` and run `start.sh`, add, count, queries with and without
`--category`, re-add some ids with new vectors and categories, delete some ids (plus a few unknown
ones), run `stop.sh` and `start.sh` again, then kill every process without `stop.sh` and run
`start.sh` again, add a few more documents. After every step the count and query results must be
right, including for the documents it changed, deleted or added. At the end it opens your data
under `/work/data` with {product}'s own client and checks the stored documents match.

You can't see the check. Tell me when the tool is done, with a short note on anything that tripped
you up.
