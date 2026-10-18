import streamlit as st
import pandas as pd
import datetime as dt
import plotly.express as px
import plotly.graph_objects as go
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# ==============================
# Database Connection
# ==============================

DATABASE_URL = st.secrets["DATABASE_URL"]


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def load_data():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM safety_observations ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return pd.DataFrame(rows)


def insert_observation(data):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO safety_observations (
            report_date, shift, area, unit, observation_type,
            hazard_category, description, immediate_action,
            likelihood, severity_letter, severity_number,
            risk_score, risk_level, risk_color,
            status, responsible_person, target_close_date,
            actual_close_date, reported_by, ai_category
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, data)

    conn.commit()
    conn.close()


def update_observation(obs_id, status, responsible, target_date, actual_date):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE safety_observations
        SET status = %s,
            responsible_person = %s,
            target_close_date = %s,
            actual_close_date = %s
        WHERE id = %s
    """, (status, responsible, target_date, actual_date, obs_id))

    conn.commit()
    conn.close()

# ==============================
# EGPC Risk Matrix
# ==============================

LIKELIHOOD = {
    1: "1 - Rare / نادر",
    2: "2 - Unlikely / غير محتمل",
    3: "3 - Possible / ممكن",
    4: "4 - Likely / محتمل",
    5: "5 - Very Likely / شبه مؤكد",
    6: "6 - Almost Certain / مؤكد تقريبًا"
}

SEVERITY = {
    "A": "A - Disastrous / كارثي",
    "B": "B - Catastrophic / كارثي جدًا",
    "C": "C - Major / كبير",
    "D": "D - Serious / جسيم",
    "E": "E - Minor / متوسط",
    "F": "F - Notable / طفيف"
}

SEVERITY_NUMBER = {
    "A": 6,
    "B": 5,
    "C": 4,
    "D": 3,
    "E": 2,
    "F": 1
}

RISK_MATRIX = {
    6: {"A": "R", "B": "R", "C": "R", "D": "O", "E": "Y", "F": "Y"},
    5: {"A": "R", "B": "R", "C": "O", "D": "O", "E": "Y", "F": "G"},
    4: {"A": "R", "B": "O", "C": "O", "D": "Y", "E": "Y", "F": "G"},
    3: {"A": "O", "B": "O", "C": "Y", "D": "Y", "E": "G", "F": "G"},
    2: {"A": "O", "B": "Y", "C": "Y", "D": "G", "E": "G", "F": "G"},
    1: {"A": "Y", "B": "Y", "C": "G", "D": "G", "E": "G", "F": "G"}
}

COLOR_NAME = {
    "G": "منخفض",
    "Y": "متوسط",
    "O": "عالي",
    "R": "حرج"
}

COLOR_HEX = {
    "G": "#2E7D32",
    "Y": "#F9A825",
    "O": "#EF6C00",
    "R": "#C62828"
}


def evaluate_risk(likelihood, severity_letter):
    severity_number = SEVERITY_NUMBER[severity_letter]
    risk_score = likelihood * severity_number
    color_code = RISK_MATRIX[likelihood][severity_letter]
    risk_level = COLOR_NAME[color_code]
    risk_color = COLOR_HEX[color_code]

    return severity_number, risk_score, risk_level, risk_color, color_code


def smart_classify(description):
    text = description.lower()

    rules = {
        "تسرب": "تسرب / إطلاق مواد",
        " leak": "تسرب / إطلاق مواد",
        "بروبيلين": "تسرب / إطلاق مواد",
        "حريق": "حريق / انفجار",
        "انفجار": "حريق / انفجار",
        "كهرباء ساكنة": "كهرباء ساكنة",
        "غبار": "غبار قابل للاشتعال / بوليمر",
        "pp": "غبار قابل للاشتعال / بوليمر",
        "بولي بروبيلين": "غبار قابل للاشتعال / بوليمر",
        "ppe": "معدات الحماية الشخصية",
        "واقي": "معدات الحماية الشخصية",
        "خوذة": "معدات الحماية الشخصية",
        "قفاز": "معدات الحماية الشخصية",
        "ارتفاع": "العمل على ارتفاع",
        "سلم": "العمل على ارتفاع",
        "مكان مغلق": "الأماكن المغلقة",
        "نيتروجين": "الأماكن المغلقة / نقص الأكسجين",
        "loto": "العزل والطاقة الخطرة",
        "عزل": "العزل والطاقة الخطرة",
        "تصريح": "تصاريح العمل",
        "permit": "تصاريح العمل",
        "ضوضاء": "الصحة المهنية / ضوضاء",
        "حرارة": "الصحة المهنية / إجهاد حراري",
        "معدات": "سلامة المعدات",
        "صمام": "سلامة المعدات / Safety Critical Equipment",
        "إنذار": "أنظمة السلامة الحرجة"
    }

    for keyword, category in rules.items():
        if keyword in text:
            return category

    return "ملاحظة عامة"

# ==============================
# Streamlit App
# ==============================

st.set_page_config(
    page_title="نظام ملاحظات السلامة",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ نظام ملاحظات السلامة والحوادث الوشيكة")
st.markdown("**شركة بتروكيماويات لإنتاج البروبيلين والبولي بروبيلين — بورسعيد**")

menu = st.sidebar.radio(
    "القائمة",
    [
        "تسجيل ملاحظة",
        "استعراض الملاحظات",
        "البحث والاسترجاع",
        "متابعة الإجراءات",
        "لوحة المؤشرات",
        "تصدير البيانات"
    ]
)

df = load_data()

# ==============================
# New Observation
# ==============================

if menu == "تسجيل ملاحظة":

    st.subheader("📝 تسجيل ملاحظة سلامة أو حادث وشيك")

    col1, col2 = st.columns(2)

    with col1:
        report_date = st.date_input("تاريخ الملاحظة", dt.date.today())
        shift = st.selectbox("الوردية", ["صباحية", "مسائية", "ليلية"])
        area = st.selectbox(
            "المنطقة",
            [
                "وحدة البروبيلين",
                "وحدة البوليمرة",
                "منطقة التخزين",
                "منطقة التعبئة",
                "الصيانة",
                "المختبر",
                "المنطقة الإدارية",
                "أخرى"
            ]
        )
        unit = st.text_input("الوحدة / المعدات")

    with col2:
        observation_type = st.selectbox(
            "نوع الملاحظة",
            [
                "سلوك آمن",
                "سلوك غير آمن",
                "وضع غير آمن",
                "حادث وشيك Near Miss",
                "مخالفة إجراءات",
                "حالة طوارئ"
            ]
        )
        hazard_category = st.selectbox(
            "تصنيف الخطر",
            [
                "تسرب / إطلاق مواد",
                "حريق / انفجار",
                "كهرباء ساكنة",
                "غبار قابل للاشتعال / بوليمر",
                "معدات الحماية الشخصية",
                "العمل على ارتفاع",
                "الأماكن المغلقة",
                "العزل والطاقة الخطرة",
                "تصاريح العمل",
                "الصحة المهنية / ضوضاء",
                "الصحة المهنية / إجهاد حراري",
                "سلامة المعدات / Safety Critical Equipment",
                "حالة غير آمنة",
                "ملاحظة عامة"
            ]
        )
        likelihood = st.selectbox(
            "احتمالية الحدوث",
            list(LIKELIHOOD.keys()),
            format_func=lambda x: LIKELIHOOD[x]
        )
        severity_letter = st.selectbox(
            "شدة الأثر",
            list(SEVERITY.keys()),
            format_func=lambda x: SEVERITY[x]
        )

    reported_by = st.text_input("اسم المُبلّغ")

    description = st.text_area("وصف الملاحظة")

    immediate_action = st.text_area("الإجراء الفوري المتخذ")

    severity_number, risk_score, risk_level, risk_color, color_code = evaluate_risk(
        likelihood, severity_letter
    )

    ai_category = smart_classify(description)

    st.markdown(
        f"""
        <div style="
            background-color:{risk_color};
            color:white;
            padding:18px;
            border-radius:10px;
            text-align:center;
            font-size:20px;
        ">
            مستوى الخطورة: {risk_level} — درجة الخطورة: {risk_score}
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("حفظ الملاحظة", type="primary", use_container_width=True):

        if not description.strip() or not reported_by.strip():
            st.error("يجب إدخال وصف الملاحظة واسم المُبلّغ.")
        else:
            data = (
                report_date,
                shift,
                area,
                unit,
                observation_type,
                hazard_category,
                description.strip(),
                immediate_action.strip(),
                likelihood,
                severity_letter,
                severity_number,
                risk_score,
                risk_level,
                color_code,
                "Open",
                "",
                None,
                None,
                reported_by.strip(),
                ai_category
            )

            insert_observation(data)
            st.success("تم حفظ الملاحظة في قاعدة البيانات المركزية ✅")

# ==============================
# View All Observations
# ==============================

elif menu == "استعراض الملاحظات":

    st.subheader("📋 جميع الملاحظات المسجلة")

    if df.empty:
        st.info("لا توجد ملاحظات حتى الآن.")
    else:
        st.dataframe(
            df[
                [
                    "id", "report_date", "shift", "area", "unit",
                    "observation_type", "hazard_category", "ai_category",
                    "likelihood", "severity_letter", "risk_score",
                    "risk_level", "status", "reported_by"
                ]
            ],
            use_container_width=True,
            height=600
        )

# ==============================
# Search and Retrieve
# ==============================

elif menu == "البحث والاسترجاع":

    st.subheader("🔎 البحث في قاعدة البيانات")

    if df.empty:
        st.info("لا توجد بيانات للبحث.")
    else:
        col1, col2, col3 = st.columns(3)

        search_text = col1.text_input("بحث في الوصف أو المعدات أو المُبلّغ")

        area_filter = col2.multiselect(
            "المنطقة",
            sorted(df["area"].dropna().unique().tolist())
        )

        status_filter = col3.multiselect(
            "الحالة",
            sorted(df["status"].dropna().unique().tolist())
        )

        risk_filter = col4 = st.multiselect(
            "مستوى الخطورة",
            sorted(df["risk_level"].dropna().unique().tolist())
        )

        filtered = df.copy()

        if search_text:
            filtered = filtered[
                filtered["description"].str.contains(search_text, case=False, na=False)
                | filtered["unit"].str.contains(search_text, case=False, na=False)
                | filtered["reported_by"].str.contains(search_text, case=False, na=False)
            ]

        if area_filter:
            filtered = filtered[filtered["area"].isin(area_filter)]

        if status_filter:
            filtered = filtered[filtered["status"].isin(status_filter)]

        if risk_filter:
            filtered = filtered[filtered["risk_level"].isin(risk_filter)]

        st.write(f"عدد النتائج: {len(filtered)}")

        st.dataframe(filtered, use_container_width=True, height=600)

# ==============================
# Follow-up
# ==============================

elif menu == "متابعة الإجراءات":

    st.subheader("✅ متابعة الإجراءات التصحيحية")

    if df.empty:
        st.info("لا توجد ملاحظات.")
    else:
        open_df = df[df["status"] != "Closed"]

        st.dataframe(
            open_df[
                [
                    "id", "report_date", "area", "unit", "observation_type",
                    "hazard_category", "risk_level", "status",
                    "responsible_person", "target_close_date"
                ]
            ],
            use_container_width=True
        )

        st.markdown("---")

        obs_id = st.number_input("رقم الملاحظة", min_value=1, step=1)

        col1, col2 = st.columns(2)

        with col1:
            status = st.selectbox(
                "الحالة الجديدة",
                ["Open", "In Progress", "Closed"]
            )
            responsible = st.text_input("المسؤول")

        with col2:
            target_date = st.date_input("الموعد المستهدف")
            actual_date = st.date_input("تاريخ الإغلاق الفعلي")

        if st.button("تحديث الملاحظة", use_container_width=True):
            update_observation(
                int(obs_id),
                status,
                responsible,
                target_date,
                actual_date if status == "Closed" else None
            )
            st.success("تم تحديث الملاحظة ✅")

# ==============================
# Dashboard
# ==============================

elif menu == "لوحة المؤشرات":

    st.subheader("📊 لوحة مؤشرات السلامة الاستباقية")

    if df.empty:
        st.info("لا توجد بيانات كافية.")
    else:
        total = len(df)
        open_count = len(df[df["status"] == "Open"])
        closed_count = len(df[df["status"] == "Closed"])
        near_miss = len(df[df["observation_type"] == "حادث وشيك Near Miss"])
        critical = len(df[df["risk_level"].isin(["عالي", "حرج"])])

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("إجمالي الملاحظات", total)
        col2.metric("مفتوحة", open_count)
        col3.metric("مغلقة", closed_count)
        col4.metric("حوادث وشيك", near_miss)
        col5.metric("عالية الخطورة", critical)

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            fig1 = px.histogram(df, x="ai_category", title="الملاحظات حسب نوع الخطر")
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            risk_order = ["منخفض", "متوسط", "عالي", "حرج"]
            risk_counts = df["risk_level"].value_counts().reindex(risk_order).fillna(0)

            color_map = {
                "منخفض": "#2E7D32",
                "متوسط": "#F9A825",
                "عالي": "#EF6C00",
                "حرج": "#C62828"
            }

            fig2 = go.Figure(
                go.Bar(
                    x=risk_counts.index,
                    y=risk_counts.values,
                    marker_color=[color_map[x] for x in risk_counts.index]
                )
            )

            fig2.update_layout(title="مستوى الخطورة")
            st.plotly_chart(fig2, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            fig3 = px.pie(df, names="area", title="الملاحظات حسب المنطقة")
            st.plotly_chart(fig3, use_container_width=True)

        with col4:
            fig4 = px.histogram(df, x="observation_type", title="أنواع الملاحظات")
            st.plotly_chart(fig4, use_container_width=True)

# ==============================
# Export
# ==============================

else:

    st.subheader("📤 تصدير البيانات")

    if df.empty:
        st.info("لا توجد بيانات.")
    else:
        csv = df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "تحميل ملف Excel/CSV",
            csv,
            "safety_observations.csv",
            "text/csv",
            use_container_width=True
        )

        st.dataframe(df, use_container_width=True)
