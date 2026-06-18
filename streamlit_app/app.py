import time
import requests
import streamlit as st

API_URL = "http://localhost:8000"

REC_LABELS = {
    "strong_fit": "Strong Fit",
    "moderate_fit": "Moderate Fit",
    "weak_fit": "Weak Fit",
    "not_a_fit": "Not a Fit",
}

COMPONENT_KEYS = [
    ("work_experience", "Work Experience"),
    ("projects", "Projects"),
    ("education", "Education"),
    ("skills", "Skills"),
    ("certifications", "Certifications"),
]


def poll_job(job_id: str, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{API_URL}/jobs/{job_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(1)
    raise TimeoutError("Evaluation timed out")


def show_api_error(resp: requests.Response) -> None:
    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        detail = resp.text
    st.error(f"API error ({resp.status_code}): {detail}")
    st.stop()


def render_scoring_breakdown(r: dict) -> None:
    breakdown = r.get("score_breakdown")
    if not breakdown:
        return
    st.subheader("Scoring Method")
    st.caption("Skills 35% · Experience 30% · Projects 15% · Education 10% · Certifications 10%")
    rows = []
    for b in breakdown:
        rows.append({
            "Component": b["component"],
            "Weight": f"{int(b['weight'] * 100)}%",
            "Raw": f"{b['raw_score']}/100",
            "Weighted": b["weighted_score"],
            "Details": b["details"],
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_extractions(r: dict) -> None:
    jd = r.get("jd_extraction")
    resume = r.get("resume_extraction")
    if not jd and not resume:
        return
    with st.expander("Extracted Data"):
        if jd:
            st.write("**From Job Description**")
            st.json(jd)
        if resume:
            st.write("**From Resume**")
            st.json(resume)


def render_components(r: dict) -> None:
    present = [(k, label) for k, label in COMPONENT_KEYS if r.get(k)]
    if not present:
        return

    st.subheader("Component Breakdown")
    cols = st.columns(len(present))
    for col, (key, label) in zip(cols, present):
        with col:
            st.metric(label, f"{r[key]['score']}/100")

    for key, label in present:
        comp = r[key]
        with st.expander(f"{label} — {comp['score']}/100"):
            st.write(comp["summary"])
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Highlights**")
                for h in comp["highlights"]:
                    st.write(f"- {h}")
            with c2:
                st.write("**Concerns**")
                for c in comp["concerns"]:
                    st.write(f"- {c}")


def render_result(r: dict, show_components: bool = True) -> None:
    method = r.get("evaluation_method", "direct")
    st.caption(f"Method: **{method}** — {'single LLM evaluation' if method == 'direct' else 'LangChain: extract → compare & score'}")

    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Fit Score", f"{r['fit_score']}/100")
        st.write(f"**{REC_LABELS.get(r['recommendation'], r['recommendation'])}**")
    with col2:
        st.subheader("Overall Reasoning")
        st.write(r["reasoning"])

    if show_components:
        render_scoring_breakdown(r)
        render_components(r)
        render_extractions(r)

    col_s, col_g = st.columns(2)
    with col_s:
        st.subheader("Strengths")
        strengths = r.get("strengths") or []
        if strengths:
            for s in strengths:
                st.write(f"- {s}")
        else:
            st.write("No strengths returned")
    with col_g:
        st.subheader("Gaps")
        gaps = r.get("gaps") or []
        if gaps:
            for g in gaps:
                st.write(f"- {g}")
        else:
            st.write("No gaps returned")


st.set_page_config(page_title="AI Resume Screener", page_icon="📄", layout="wide")
st.title("AI Resume Screener")
st.caption("Upload a job description and resume PDF to get a fit score with reasoning.")

with st.sidebar:
    st.header("Settings")
    api_url = st.text_input("API URL", value=API_URL)
    if api_url:
        API_URL = api_url.rstrip("/")
    eval_mode = st.selectbox(
        "Evaluation method",
        options=["direct", "pipeline"],
        format_func=lambda x: "Direct (single LLM)" if x == "direct" else "Pipeline (extract + score)",
        index=0,
    )
    try:
        health = requests.get(f"{API_URL}/health", timeout=5).json()
        if health.get("groq_configured"):
            st.success(f"API connected · {health.get('model', 'groq')}")
        else:
            st.warning("API connected but GROQ_API_KEY is missing. Add it to `.env` and restart the API.")
    except requests.RequestException:
        st.error("Cannot reach API. Start it with: `uvicorn app.main:create_app --factory --reload`")

tab_single, tab_batch = st.tabs(["Single Resume", "Batch Upload"])

with tab_single:
    job_desc = st.text_area("Job Description", height=200, placeholder="Paste the job description here...")
    resume_file = st.file_uploader("Resume (PDF)", type=["pdf"], key="single")

    if st.button("Evaluate Fit", type="primary", disabled=not (job_desc and resume_file)):
        with st.spinner("Evaluating..."):
            files = {"resume": (resume_file.name, resume_file.getvalue(), "application/pdf")}
            data = {"job_description": job_desc, "mode": eval_mode}
            resp = requests.post(f"{API_URL}/evaluate", data=data, files=files, timeout=30)
            if not resp.ok:
                show_api_error(resp)
            job_id = resp.json()["job_id"]

            try:
                result = poll_job(job_id)
            except TimeoutError:
                st.error("Evaluation timed out. Check API logs.")
                st.stop()

            if result["status"] == "failed":
                st.error(result.get("error", "Evaluation failed"))
            else:
                render_result(result["result"])

with tab_batch:
    job_desc_batch = st.text_area("Job Description", height=200, key="batch_jd")
    resume_files = st.file_uploader(
        "Resumes (PDF)", type=["pdf"], accept_multiple_files=True, key="batch"
    )

    if st.button("Evaluate All", type="primary", disabled=not (job_desc_batch and resume_files)):
        with st.spinner(f"Queuing {len(resume_files)} resumes..."):
            files = [
                ("resumes", (f.name, f.getvalue(), "application/pdf")) for f in resume_files
            ]
            data = {"job_description": job_desc_batch, "mode": eval_mode}
            resp = requests.post(f"{API_URL}/evaluate/batch", data=data, files=files, timeout=60)
            if not resp.ok:
                show_api_error(resp)
            job_ids = resp.json()["job_ids"]

        progress = st.progress(0)
        results = []
        for i, job_id in enumerate(job_ids):
            try:
                result = poll_job(job_id)
                results.append((resume_files[i].name, result))
            except TimeoutError:
                results.append((resume_files[i].name, {"status": "failed", "error": "timeout"}))
            progress.progress((i + 1) / len(job_ids))

        completed = [r for _, r in results if r.get("status") == "completed"]
        if completed:
            ranked = sorted(
                [(name, r["result"]) for name, r in results if r.get("status") == "completed"],
                key=lambda x: x[1]["fit_score"],
                reverse=True,
            )
            st.subheader("Ranked Results")
            for name, r in ranked:
                with st.expander(f"{name} — {r['fit_score']}/100 ({REC_LABELS.get(r['recommendation'], '')})"):
                    render_result(r, show_components=True)

        failed = [(name, r) for name, r in results if r.get("status") == "failed"]
        if failed:
            st.warning(f"{len(failed)} evaluation(s) failed")
            for name, r in failed:
                st.write(f"- {name}: {r.get('error', 'unknown error')}")
