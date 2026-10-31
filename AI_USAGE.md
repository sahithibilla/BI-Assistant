# AI Usage Notes

**Tools used:** Claude (chat) for design, code generation and test drafting.

**How AI was used:** discussed the design, generated the first version of the modules, then reviewed and ran everything locally. I chose the intent-routing design myself over text-to-SQL to guarantee safety and correctness.

**Problems encountered & debugging**
1. *Dirty data* – found TXN0033 (Returned), TXN0034 (qty 0) and TXN0051 (missing price) by inspecting the CSV; added an `is_valid` flag + reason instead of deleting rows.
2. *Date format* – DD-MM-YYYY is ambiguous with MM-DD; fixed with an explicit format so months group correctly.
3. *Month names* – "may" is also a normal word and abbreviations clash; handled with word-boundary regex and special-casing "may".
4. *Verifying correctness* – cross-checked the total in a test against an independent SQL calculation.

**With another day:** LLM-generated narrative summaries over the returned rows, filters (product/region/date range), chart in the UI, refund-netting option, Docker, evaluation set for the interpreter, and a validated read-only text-to-SQL mode.

