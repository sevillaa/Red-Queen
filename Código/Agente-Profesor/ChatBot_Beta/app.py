from pathlib import Path
import streamlit as st
from rag_system import query_rag, query_rag_labs

st.set_page_config(page_title="Profesor de Redes y Seguridad", page_icon="👨‍🏫", layout="wide")

CARPETA_LABS = Path(__file__).resolve().parent / "Labs"

if "chats" not in st.session_state:
    st.session_state.chats = {}
if "seccion" not in st.session_state:
    st.session_state.seccion = "Temario"
if "practica" not in st.session_state:
    st.session_state.practica = None

practicas = sorted((p.stem for p in CARPETA_LABS.glob("*.pdf")), key=str.casefold) if CARPETA_LABS.exists() else []

with st.sidebar:
    st.title("👨‍🏫 Profesor RyS")
    st.caption("Elige qué quieres estudiar")
    seccion = st.radio("Navegación", ["Temario", "Prácticas"], key="seccion")
    practica = None
    if seccion == "Prácticas":
        if practicas:
            if st.session_state.practica not in practicas:
                st.session_state.practica = practicas[0]
            practica = st.selectbox("Selecciona una práctica", practicas, key="practica")
            st.info(f"📌 Trabajando en: {practica}")
        else:
            st.warning("No se encontraron PDFs en la carpeta Labs.")
    chat_id = "temario" if seccion == "Temario" else f"practica::{practica}"
    st.divider()
    if st.button("🗑️ Limpiar este chat", use_container_width=True, disabled=(seccion == "Prácticas" and not practica)):
        st.session_state.chats[chat_id] = []
        st.rerun()
    st.caption("Los historiales se mantienen separados durante esta sesión.")

st.title("📚 Consultas del temario" if seccion == "Temario" else "🧪 Asistente de prácticas")
if seccion == "Prácticas":
    if not practica:
        st.info("Añade archivos PDF a la carpeta Labs para seleccionar una práctica.")
        st.stop()
    st.caption(f"Práctica activa: **{practica}**. El asistente te guía sin resolver directamente los ejercicios.")
else:
    st.caption("Haz preguntas sobre los documentos de teoría de Redes y Seguridad.")
st.divider()

mensajes = st.session_state.chats.setdefault(chat_id, [])
col_chat, col_docs = st.columns([2, 1])
with col_chat:
    st.subheader("💬 Chat")
    for mensaje in mensajes:
        with st.chat_message(mensaje["role"]):
            st.markdown(mensaje["content"])
with col_docs:
    st.subheader("📄 Documentos relevantes")
    ultima_respuesta = next((m for m in reversed(mensajes) if m["role"] == "assistant"), None)
    docs = ultima_respuesta.get("docs", []) if ultima_respuesta else []
    if not docs:
        st.caption("Aquí aparecerán los fragmentos usados en la última respuesta.")
    for doc in docs:
        with st.expander(f"📄 Fragmento {doc['fragmento']}"):
            st.markdown(f"**Fuente:** {doc['fuente']}")
            st.markdown(f"**Página:** {doc['pagina']}")
            st.text(doc["contenido"])

pregunta = st.chat_input("Pregunta sobre el temario..." if seccion == "Temario" else f"Pregunta sobre {practica}...")
if pregunta:
    # La conversación anterior se envía solo desde el chat activo.
    historial_previo = mensajes[-10:]
    mensajes.append({"role": "user", "content": pregunta})
    with st.spinner("🔍 Consultando documentos..."):
        if seccion == "Temario":
            respuesta, docs = query_rag(pregunta, historial_previo)
        else:
            respuesta, docs = query_rag_labs(pregunta, practica, historial_previo)
    mensajes.append({"role": "assistant", "content": respuesta, "docs": docs})
    st.rerun()
