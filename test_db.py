import streamlit as st
import psycopg2

st.title("اختبار الاتصال بقاعدة البيانات")

try:
    conn = psycopg2.connect(
        st.secrets["DATABASE_URL"],
        sslmode="require",
        connect_timeout=15
    )
    st.success("تم الاتصال بقاعدة البيانات بنجاح ✅")
    conn.close()

except Exception as e:
    st.error("فشل الاتصال بقاعدة البيانات ❌")
    st.code(str(e))
