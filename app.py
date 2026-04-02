"""
Culmen — Bird ID Quiz
Test your ability to tell similar species apart using Macaulay Library photos and eBird data.
"""

import random
import requests
import streamlit as st

st.set_page_config(
    page_title="Culmen — Bird ID Quiz",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

EBIRD_BASE = "https://api.ebird.org/v2"
MACAULAY_SEARCH = "https://search.macaulaylibrary.org/api/v1/search"
MACAULAY_CDN = "https://cdn.download.ams.birds.cornell.edu/api/v2/asset"
AAB_GUIDE = "https://www.allaboutbirds.org/guide"

LOGO_SVG = """<svg width="160" height="96" viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg">
  <path d="M20,60 Q60,20 100,50 L140,20" stroke="#333" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="55" cy="45" r="5" fill="#333"/>
  <text x="100" y="110" font-family="Helvetica, Arial, sans-serif" font-size="28" fill="#333" text-anchor="middle">Culmen</text>
</svg>"""


def ebird_headers() -> dict:
    key = st.secrets.get("EBIRD_API_KEY", "")
    return {"X-eBirdApiToken": key} if key else {}


def has_api_key() -> bool:
    return bool(st.secrets.get("EBIRD_API_KEY", ""))


@st.cache_data(ttl=86400, show_spinner="Loading eBird taxonomy…")
def load_taxonomy() -> dict:
    """Returns {ALPHA_CODE: (speciesCode, comName)}"""
    resp = requests.get(
        f"{EBIRD_BASE}/ref/taxonomy/ebird",
        headers=ebird_headers(),
        params={"fmt": "json"},
        timeout=60,
    )
    resp.raise_for_status()
    lookup = {}
    for sp in resp.json():
        for code in sp.get("bandingCodes", []):
            lookup[code.upper()] = (sp["speciesCode"], sp["comName"])
    return lookup


@st.cache_data(ttl=3600, show_spinner="Fetching recent DC sightings…")
def get_dc_species() -> list:
    resp = requests.get(
        f"{EBIRD_BASE}/data/obs/US-DC/recent",
        headers=ebird_headers(),
        params={"maxResults": 200},
        timeout=15,
    )
    if not resp.ok:
        return []
    seen = {}
    for o in resp.json():
        code = o.get("speciesCode")
        if code and code not in seen:
            seen[code] = {"speciesCode": code, "comName": o.get("comName", code)}
    return sorted(seen.values(), key=lambda x: x["comName"])


@st.cache_data(ttl=3600, show_spinner="Fetching photos…")
def get_photos(species_code: str, count: int = 10) -> list:
    resp = requests.get(
        MACAULAY_SEARCH,
        params={
            "taxonCode": species_code,
            "mediaType": "p",
            "count": count,
            "sort": "rating_rank_desc",
        },
        timeout=15,
    )
    if not resp.ok:
        return []
    content = resp.json().get("results", {}).get("content", [])
    return [f"{MACAULAY_CDN}/{r['assetId']}/1800" for r in content if r.get("assetId")]


def lookup_species(alpha: str, taxonomy: dict):
    return taxonomy.get(alpha.upper().strip(), (None, None))


def aab_url(common_name: str) -> str:
    return f"{AAB_GUIDE}/{common_name.replace(' ', '_')}/id"


def init_quiz(sp1_name, sp1_code, sp2_name, sp2_code, num_photos):
    photos1 = get_photos(sp1_code, num_photos)
    photos2 = get_photos(sp2_code, num_photos)
    if not photos1:
        st.error(f"No photos found for {sp1_name}")
        return
    if not photos2:
        st.error(f"No photos found for {sp2_name}")
        return
    quiz = [(url, sp1_name) for url in photos1] + [(url, sp2_name) for url in photos2]
    random.shuffle(quiz)
    st.session_state.update(
        quiz=quiz,
        quiz_idx=0,
        score=0,
        answers=[],
        sp1_name=sp1_name,
        sp2_name=sp2_name,
        sp1_code=sp1_code,
        sp2_code=sp2_code,
    )


def _record_answer(guess, correct):
    is_correct = guess == correct
    if is_correct:
        st.session_state.score += 1
    st.session_state.answers.append({
        "url": st.session_state.quiz[st.session_state.quiz_idx][0],
        "correct": correct,
        "guess": guess,
        "ok": is_correct,
    })
    st.session_state.quiz_idx += 1
    st.rerun()


def quiz_view():
    quiz = st.session_state.quiz
    idx = st.session_state.quiz_idx
    sp1 = st.session_state.sp1_name
    sp2 = st.session_state.sp2_name

    if idx >= len(quiz):
        results_view()
        return

    url, correct = quiz[idx]
    total = len(quiz)

    col_img, col_aside = st.columns([2, 1])

    with col_img:
        st.progress(idx / total, text=f"Photo {idx + 1} of {total}  •  Score: {st.session_state.score}/{idx}")
        st.image(url, use_container_width=True)
        btn1, btn2 = st.columns(2)
        with btn1:
            if st.button(sp1, key=f"a_{idx}", use_container_width=True, type="primary"):
                _record_answer(sp1, correct)
        with btn2:
            if st.button(sp2, key=f"b_{idx}", use_container_width=True, type="primary"):
                _record_answer(sp2, correct)

    with col_aside:
        st.markdown("### ID Tips")
        st.markdown(f"- [{sp1}]({aab_url(sp1)}) — All About Birds")
        st.markdown(f"- [{sp2}]({aab_url(sp2)}) — All About Birds")
        q = f"{sp1.replace(' ', '+')}+vs+{sp2.replace(' ', '+')}"
        st.markdown(f"- [Google: {sp1} vs {sp2}](https://www.google.com/search?q={q}+identification+difference)")
        st.markdown(f"- [eBird: {sp1}](https://ebird.org/species/{st.session_state.sp1_code})")
        st.markdown(f"- [eBird: {sp2}](https://ebird.org/species/{st.session_state.sp2_code})")


def results_view():
    score = st.session_state.score
    total = len(st.session_state.quiz)
    pct = int(100 * score / total)

    st.markdown(f"## Quiz Complete — {score}/{total} ({pct}%)")
    if pct == 100:
        st.success("Perfect score!")
    elif pct >= 80:
        st.success("Great job!")
    elif pct >= 60:
        st.info("Not bad — review the ones you missed below.")
    else:
        st.warning("Keep practicing!")

    wrong = [a for a in st.session_state.answers if not a["ok"]]
    if wrong:
        st.markdown("### Missed Photos")
        for i in range(0, len(wrong), 3):
            cols = st.columns(3)
            for j, a in enumerate(wrong[i : i + 3]):
                with cols[j]:
                    st.image(a["url"], use_container_width=True)
                    st.caption(f"You said: **{a['guess']}**\nCorrect: {a['correct']}")

    if st.button("New Quiz", type="primary"):
        for k in ["quiz", "quiz_idx", "score", "answers", "sp1_name", "sp2_name", "sp1_code", "sp2_code"]:
            st.session_state.pop(k, None)
        st.rerun()


def main():
    st.markdown(LOGO_SVG, unsafe_allow_html=True)

    if not has_api_key():
        st.warning(
            "No eBird API key found. Add `EBIRD_API_KEY = 'your_key'` to "
            "`.streamlit/secrets.toml`. Get a free key at https://ebird.org/api/keygen"
        )

    with st.sidebar:
        st.markdown("## Quiz Setup")
        st.caption("Enter 4-letter AOU alpha codes, e.g. HOFI, PUFI")
        code1 = st.text_input("Bird 1", value="HOFI", max_chars=6).upper().strip()
        code2 = st.text_input("Bird 2", value="PUFI", max_chars=6).upper().strip()
        num_photos = st.slider("Photos per species", min_value=5, max_value=20, value=10)

        if st.button("Start Quiz", type="primary", use_container_width=True):
            taxonomy = load_taxonomy()
            sp1_code, sp1_name = lookup_species(code1, taxonomy)
            sp2_code, sp2_name = lookup_species(code2, taxonomy)
            if not sp1_code:
                st.error(f"Alpha code '{code1}' not found in eBird taxonomy.")
            elif not sp2_code:
                st.error(f"Alpha code '{code2}' not found in eBird taxonomy.")
            elif sp1_code == sp2_code:
                st.error("Both codes resolve to the same species.")
            else:
                init_quiz(sp1_name, sp1_code, sp2_name, sp2_code, num_photos)

        st.divider()
        st.markdown("### Recent DC Sightings")
        if has_api_key():
            dc_birds = get_dc_species()
            if dc_birds:
                for bird in dc_birds[:40]:
                    st.caption(f"• {bird['comName']}")
            else:
                st.caption("Could not load DC sightings.")
        else:
            st.caption("Add eBird API key to see what's been spotted in DC.")

    if "quiz" in st.session_state:
        quiz_view()
    else:
        st.markdown("""
## Welcome to Culmen

Test your ability to tell similar bird species apart using real photos from the
[Macaulay Library](https://www.macaulaylibrary.org/) at the Cornell Lab of Ornithology.

**How to play:**
1. Enter two 4-letter alpha codes in the sidebar (e.g. `HOFI` vs `PUFI`)
2. Click **Start Quiz**
3. Identify each photo — is it species 1 or species 2?
4. Review your score and missed photos at the end

The sidebar also shows birds recently spotted in DC via [eBird](https://ebird.org) —
great for picking pairs to practice.

---
*Photos and data from the [Cornell Lab of Ornithology](https://www.birds.cornell.edu/).*
        """)


if __name__ == "__main__":
    main()
