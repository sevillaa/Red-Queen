import streamlit as st
from rag_system import query_rag

# Configuración de la página
st.set_page_config(
    page_title="Sistema RAG - Profesor de Universidad",
    page_icon="👨‍🏫",
    layout="wide"
)

# Título
st.title("👨‍🏫 Profesor de Universidad RyS")
st.divider()

# Inicializar el historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar simplificado
with st.sidebar:
    st.header("📋 Información del Sistema")
    
    st.markdown("**🤖 Modelos:**")
    st.info("Consultas: GPT-4o-mini\nRespuestas: GPT-4o")
    
    st.divider()
    
    if st.button("🗑️ Limpiar Chat", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# Layout principal con columnas
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 💬 Chat")
    
    # Mostrar historial de mensajes
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

with col2:
    st.markdown("### 📄 Documentos Relevantes")
    
    # Mostrar documentos de la última consulta
    if st.session_state.messages:
        last_message = st.session_state.messages[-1]
        if last_message["role"] == "assistant" and "docs" in last_message:
            docs = last_message["docs"]
            
            if docs:
                for doc in docs:
                    with st.expander(f"📄 Fragmento {doc['fragmento']}", expanded=False):
                        st.markdown(f"**Fuente:** {doc['fuente']}")
                        st.markdown(f"**Página:** {doc['pagina']}")
                        st.markdown("**Contenido:**")
                        st.text(doc['contenido'])

# Input del usuario
if prompt := st.chat_input("Escribe tu consulta sobre el temario de RyS..."):
    # Añadir mensaje del usuario al historial
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Generar respuesta
    with st.spinner("🔍 Analizando..."):
        response, docs = query_rag(prompt)
        st.session_state.messages.append({"role": "assistant", "content": response, "docs": docs})
    
    # Recargar para mostrar los nuevos mensajes
    st.rerun()

# Footer
st.divider()
st.markdown(
    "<div style='text-align: center; color: #666;'>👨‍🏫 Profesor de Universidad con MMR Retriever</div>", 
    unsafe_allow_html=True
)