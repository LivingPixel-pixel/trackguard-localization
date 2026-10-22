# Rebuild the pitch

The six-slide pitch is distributed as editable PowerPoint, PDF and standalone HTML. It uses native text, vector diagrams, tables and a measured real-track cover. The HTML embeds the real replay GIF and works offline.

On Windows with Microsoft PowerPoint installed:

```powershell
python -m pip install -r slides/requirements.txt
python slides/build.py
python slides/verify.py
```

The build reads the approved aggregate JSON. Verification checks six pages, metric parity, text overflow, embedded relationships and slide navigation. Generated intermediate files and QA renders stay local and are ignored by Git. The exported files in `slides/` are the release artifacts.

The intended presentation is a customer pilot brief. Its four-week schedule and pilot acceptance thresholds are proposals. They are not measured customer outcomes or delivery guarantees. The track replay is sealed R16 development evidence with evaluator-only reference truth. Architecture diagrams remain illustrative.
