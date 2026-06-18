# AI Resume Screener

Upload a job description + resume PDF → structured fit score with reasoning.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:create_app --factory --reload --port 8000
streamlit run streamlit_app/app.py
```

## Structure

```
app/
  main.py           FastAPI entry
  config.py         env settings + LangSmith setup
  api/routes.py     HTTP endpoints
  core/queue.py     async job queue
  models/schemas.py all Pydantic models
  services/
    evaluator.py    routes PDF → direct or pipeline
    direct.py       single Groq call
    pipeline.py     LangChain 3-step chain
    scoring.py      weighted score math + strengths/gaps fill
    groq.py         Groq API client (direct mode)
    pdf.py          PDF text extraction
streamlit_app/app.py  UI
```

## Config (.env)

`GROQ_API_KEY`, `GROQ_MODEL`, `EVALUATION_MODE` (direct|pipeline), `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
