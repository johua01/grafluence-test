import streamlit as st
import pandas as pd
import random
import gspread
from collections import Counter
from oauth2client.service_account import ServiceAccountCredentials

# ------------------- CONFIG -------------------
SHEET_NAME = "grafluence_test"
EXCEL_FILE = "grafluence_data.xlsx"
PRICE_SHEET = "small_sample_prices"
IMAGE_SHEET = "brand_images_real"
CREDENTIALS_FILE = "grafluence-73d7a0c57.json"

# ------------------- BRAND CLUSTERS -------------------
BRAND_CLUSTERS = {
    "GUCCI": 1, "SAINT LAURENT": 1, "ALEXANDER MCQUEEN": 1, "TOM FORD": 1, "MAISON MARGIELA": 1, "RICK OWENS": 1, "YOHJI YAMAMOTO": 1,
    "OFF-WHITE": 2, "SUPREME": 2, "PALM ANGELS": 2, "FEAR OF GOD": 2,
    "THE FRANKIE SHOP": 3, "A.P.C.": 3, "VINCE": 3, "NANUSHKA": 3, "RAG & BONE": 3, "POLO RALPH LAUREN": 3,
    "NIKE": 4, "ADIDAS": 4, "THE NORTH FACE": 4, "LULULEMON": 4,
    "LEVI'S": 5, "AGOLDE": 5, "7 FOR ALL MANKIND": 5, "CALVIN KLEIN JEANS": 5,
    "ZIMMERMANN": 6, "JOHANNA ORTIZ": 6, "SOLID & STRIPED": 6, "HUNZA G": 6,
    "MICHAEL KORS COLLECTION": 7, "VERSACE JEANS COUTURE": 7, "CALVIN KLEIN JEANS": 7, "POLO RALPH LAUREN": 7
}

# ------------------- LOAD DATA -------------------
@st.cache_data
def load_data():
    prices = pd.read_excel(EXCEL_FILE, sheet_name=PRICE_SHEET)
    images = pd.read_excel(EXCEL_FILE, sheet_name=IMAGE_SHEET)

    prices["Brand"] = prices["Brand"].str.upper()
    images["Brand"] = images["Brand"].str.upper()
    images = images.dropna(subset=["Product image URL"])

    weighted_lookup = {}
    for brand, group in images.groupby("Brand"):
        category_counts = Counter(group["Category 2"])
        weights = group["Category 2"].map(lambda x: category_counts[x])
        weighted_lookup[brand] = list(zip(group["Product image URL"], weights))

    price_lookup = dict(zip(prices["Brand"], prices["Average Price"]))
    available_brands = list(set(price_lookup) & set(weighted_lookup))
    return available_brands, price_lookup, weighted_lookup

brands, price_lookup, image_lookup = load_data()

# ------------------- SESSION STATE -------------------
if "page" not in st.session_state:
    st.session_state.page = "start"
if "questions" not in st.session_state:
    st.session_state.questions = [None] * 30
if "index" not in st.session_state:
    st.session_state.index = 0
if "responses" not in st.session_state:
    st.session_state.responses = []

# ------------------- QUESTION GENERATORS -------------------
def weighted_sample(images, k=6):
    urls, weights = zip(*images)
    return random.choices(urls, weights=weights, k=min(k, len(urls)))

def get_brand_data(brand):
    images = weighted_sample(image_lookup[brand])
    return {
        "Brand": brand,
        "Price": round(price_lookup[brand]),
        "Images": images
    }

def generate_cluster_question(verify_cluster, test_cluster):
    reference = random.choice([b for b in brands if BRAND_CLUSTERS.get(b) == verify_cluster])
    same = random.choice([b for b in brands if BRAND_CLUSTERS.get(b) == verify_cluster and b != reference])
    different = random.choice([b for b in brands if BRAND_CLUSTERS.get(b) == test_cluster])
    if random.random() < 0.5:
        return {"reference": get_brand_data(reference), "a": get_brand_data(same), "b": get_brand_data(different)}
    else:
        return {"reference": get_brand_data(reference), "a": get_brand_data(different), "b": get_brand_data(same)}

def generate_mixed_cluster_question():
    selected_clusters = random.sample(list(set(BRAND_CLUSTERS.values())), 3)
    selected_brands = [random.choice([b for b in brands if BRAND_CLUSTERS.get(b) == c]) for c in selected_clusters]
    random.shuffle(selected_brands)
    return {
        "reference": get_brand_data(selected_brands[0]),
        "a": get_brand_data(selected_brands[1]),
        "b": get_brand_data(selected_brands[2])
    }

def generate_all_questions():
    questions = []
    all_clusters = list(set(BRAND_CLUSTERS.values()))
    all_pairs = [(v, t) for v in all_clusters for t in all_clusters if v != t]
    cluster_pairs = random.sample(all_pairs, 4)
    cluster_pairs += random.choices(all_pairs, k=16)
    for verify, test in cluster_pairs:
        questions.append(generate_cluster_question(verify, test))
    for _ in range(10):
        questions.append(generate_mixed_cluster_question())
    return questions

# ------------------- SURVEY FLOW -------------------
def record_response(q, selected, other):
    st.session_state.responses.append({
        "question": st.session_state.index + 1,
        "reference": q['reference']['Brand'],
        "selected": selected,
        "other": other
    })
    st.session_state.index += 1
    if st.session_state.index >= len(st.session_state.questions):
        st.session_state.page = "end"
    st.rerun()

def save_to_google_sheet(df):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        gcp_secrets = st.secrets["gcp_service_account"]
        credentials_dict = {
            "type": gcp_secrets["type"],
            "project_id": gcp_secrets["project_id"],
            "private_key_id": gcp_secrets["private_key_id"],
            "private_key": gcp_secrets["private_key"].replace("\\n", "\n"),
            "client_email": gcp_secrets["client_email"],
            "client_id": gcp_secrets["client_id"],
            "auth_uri": gcp_secrets["auth_uri"],
            "token_uri": gcp_secrets["token_uri"],
            "auth_provider_x509_cert_url": gcp_secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": gcp_secrets["client_x509_cert_url"],
            "universe_domain": gcp_secrets["universe_domain"]
        }
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1

        existing = sheet.get_all_values()
        if len(existing) == 0:
            sheet.append_row(df.columns.tolist())
        for _, row in df.iterrows():
            sheet.append_row([str(cell) if pd.notna(cell) else "" for cell in row.tolist()])
        st.success("✅ Survey completed!")
    except Exception as e:
        st.error(f"Failed to save to Google Sheets: {e}")

# ------------------- UI PAGES -------------------
def show_start_page():
    st.title("👕 Brand Similarity Survey")
    st.write("You'll be shown a reference clothing brand and asked which of two other brands is more similar in style and price.")
    st.write("Each question includes sample images and average prices.")
    st.write("The survey takes about **2–3 minutes**.")
    if st.button("Start Survey"):
        st.session_state.page = "survey"
        st.session_state.questions = generate_all_questions()
        st.session_state.index = 0
        st.session_state.responses = []
        st.rerun()

def show_question_page():
    i = st.session_state.index
    q = st.session_state.questions[i]

    st.markdown(f"<h2 style='text-align: center;'>Question {i + 1} of 30</h2>", unsafe_allow_html=True)

    # Reference Brand
    ref_imgs = "".join([
        f"<img src='{url}' width='80' style='margin: 4px; border-radius: 6px;'/>" for url in q['reference']['Images']
    ])
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align: center;'>
        <h3>Reference Brand: {q['reference']['Brand']}</h3>
        <p style='font-size: 18px;'><strong>Average Price:</strong> ${q['reference']['Price']}</p>
        <br/>{ref_imgs}
    </div>""", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("<h4 style='text-align: center;'>Which brand is more similar to the reference brand?</h4>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    for col, key in zip([col1, col2], ['a', 'b']):
        with col:
            img_tags = "".join([
                f"<img src='{url}' width='90' style='margin:4px; border-radius:6px;'/>" for url in q[key]["Images"]
            ])
            st.markdown(f"""
            <div style='border:2px solid #ccc; border-radius:12px; padding:16px; text-align:center;'>
                <h4>{q[key]['Brand']}</h4>
                <p style='font-size:18px;'><strong>Average Price:</strong> ${q[key]['Price']}</p>
                {img_tags}
            </div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"Select {q[key]['Brand']}", key=f"{key}_{i}"):
                record_response(q, q[key]['Brand'], q['a']['Brand'] if key == 'b' else q['b']['Brand'])

def show_end_page():
    st.title("🎉 Thank You!")
    st.markdown("""
    You’ve completed the survey — we really appreciate your time and feedback!

    Your responses will help us improve how we match influencers to brands in the fashion space.

    Feel free to close this page. ✨
    """)
    df = pd.DataFrame(st.session_state.responses)
    save_to_google_sheet(df)

# ------------------- ROUTER -------------------
if st.session_state.page == "start":
    show_start_page()
elif st.session_state.page == "survey":
    show_question_page()
elif st.session_state.page == "end":
    show_end_page()
