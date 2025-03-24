import streamlit as st
import pandas as pd
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ------------------- CONFIG -------------------
SHEET_NAME = "grafluence_test"
EXCEL_FILE = "grafluence_data.xlsx"
PRICE_SHEET = "small_sample_prices"
IMAGE_SHEET = "brand_images_real"
CREDENTIALS_FILE = "grafluence-73d7a0c01c57.json"

# ------------------- LOAD DATA -------------------
@st.cache_data
def load_data():
    prices = pd.read_excel(EXCEL_FILE, sheet_name=PRICE_SHEET)
    images = pd.read_excel(EXCEL_FILE, sheet_name=IMAGE_SHEET)

    prices["Brand"] = prices["Brand"].str.upper()
    images["Brand"] = images["Brand"].str.upper()
    images = images.dropna(subset=["Product image URL"])

    price_lookup = dict(zip(prices["Brand"], prices["Average Price"]))
    image_lookup = images.groupby("Brand")["Product image URL"].apply(list).to_dict()

    brands = list(set(price_lookup.keys()) & set(image_lookup.keys()))
    return brands, price_lookup, image_lookup

brands, price_lookup, image_lookup = load_data()

# ------------------- SESSION STATE -------------------
if "page" not in st.session_state:
    st.session_state.page = "start"
if "questions" not in st.session_state:
    st.session_state.questions = [None] * 20
if "index" not in st.session_state:
    st.session_state.index = 0
if "responses" not in st.session_state:
    st.session_state.responses = []

# ------------------- HELPERS -------------------
def generate_survey_question():
    selected = random.sample(brands, 3)

    def get_brand_data(brand):
        images = image_lookup[brand]
        sampled_images = random.sample(images, min(6, len(images)))
        return {
            "Brand": brand,
            "Price": round(price_lookup[brand]),
            "Images": sampled_images
        }

    return {
        "reference": get_brand_data(selected[0]),
        "a": get_brand_data(selected[1]),
        "b": get_brand_data(selected[2])
    }

def record_response(q, selected, other):
    st.session_state.responses.append({
        "question": st.session_state.index + 1,
        "reference": q['reference']['Brand'],
        "selected": selected,
        "other": other
    })
    st.session_state.index += 1
    if st.session_state.index >= 20:
        st.session_state.page = "end"
    st.rerun()

def save_to_google_sheet(df):
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1

        existing = sheet.get_all_values()
        if len(existing) == 0:
            sheet.append_row(df.columns.tolist())

        for _, row in df.iterrows():
            row_data = [str(cell) if pd.notna(cell) else "" for cell in row.tolist()]
            sheet.append_row(row_data)

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
        st.session_state.questions = [generate_survey_question() for _ in range(20)]
        st.session_state.index = 0
        st.session_state.responses = []
        st.rerun()

def show_question_page():
    
    i = st.session_state.index
    if st.session_state.questions[i] is None:
        st.session_state.questions[i] = generate_survey_question()
    q = st.session_state.questions[i]

    st.markdown(f"<h2 style='text-align: center;'>Question {i + 1} of 20</h2>", unsafe_allow_html=True)

    # Reference Brand
    ref_imgs = "".join(
        [f"<img src='{url}' width='80' style='margin: 4px; border-radius: 6px;'/>" for url in q['reference']["Images"]]
    )
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align: center;'>
        <h3>Reference Brand: {q['reference']['Brand']}</h3>
        <p style='font-size: 18px;'><strong>Average Price:</strong> ${q['reference']['Price']}</p>
        <br/>
        {ref_imgs}
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")


    # Comparison Brands
    st.markdown("<h4 style='text-align: center;'>Which brand is more similar to the reference brand?</h4>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        img_tags_a = "".join(
            [f"<img src='{url}' width='90' style='margin:4px; border-radius:6px;'/>" for url in q['a']["Images"]]
        )

        st.markdown(f"""
            <div style='border:2px solid #ccc; border-radius:12px; padding:16px; text-align:center;'>
                <h4>{q['a']['Brand']}</h4>
                <p style='font-size:18px;'><strong>Average Price:</strong> ${q['a']['Price']}</p>
                {img_tags_a}
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)  # Line break

        if st.button(f"Select {q['a']['Brand']}", key=f"a_{i}"):
            record_response(q, q['a']['Brand'], q['b']['Brand'])



  

    with col2:
        img_tags_b = "".join(
            [f"<img src='{url}' width='90' style='margin:4px; border-radius:6px;'/>" for url in q['b']["Images"]]
        )

        st.markdown(f"""
            <div style='border:2px solid #ccc; border-radius:12px; padding:16px; text-align:center;'>
                <h4>{q['b']['Brand']}</h4>
                <p style='font-size:18px;'><strong>Average Price:</strong> ${q['b']['Price']}</p>
                {img_tags_b}
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)  # Line break

        if st.button(f"Select {q['b']['Brand']}", key=f"b_{i}"):
            record_response(q, q['b']['Brand'], q['a']['Brand'])









        





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
