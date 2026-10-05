# Loughran-McDonald word lists - illustrative subset

`negative.txt` and `uncertainty.txt` here are a **curated subset**
(~140 and ~100 words) of the two Loughran-McDonald sentiment categories
actually used by `drift/tone.py`, written from general knowledge of
what those categories contain - **not** the full, published LM Master
Dictionary (which has roughly 2,000+ words across 7 categories and is
the real academic standard for 10-K textual analysis).

For a production-quality version, download the real Master Dictionary
from the University of Notre Dame's Software Repository for Accounting
and Finance (https://sraf.nd.edu/loughranmcdonald-master-dictionary/)
and swap these two files for the "Negative" and "Uncertainty" columns
from it. Until then, `neg_ratio`/`unc_ratio` in `tone_stats` are a
directionally-useful but approximate signal, not the validated academic
metric - noted as a limitation in docs/METHODOLOGY.md.
