import os
from pathlib import Path

import streamlit as st
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_classic.retrievers import MultiQueryRetriever, EnsembleRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from prompts import MULTI_QUERY_PROMPT, RAG_TEMPLATE, RAG_TEMPLATE_PRACTICAS

BASE_DIR = Path(__file__).resolve().parent
EMBEDDING_MODEL = "text-embedding-3-large"


def _formatear_documentos(docs):
    if not docs:
        return "No se han recuperado documentos."
    resultado = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata
        nombre = Path(meta.get("source", "Desconocido")).name
        pagina = meta.get("page", 0) + 1
        tema = meta.get("tema", "")
        lab = meta.get("lab", "")
        resultado.append(f"[Fragmento {i}] - Fuente: {nombre} - Página: {pagina} - Tema: {tema} - Práctica: {lab}\n{doc.page_content.strip()}")
    return "\n\n".join(resultado)


def _mostrar_documentos(docs):
    return [{
        "fragmento": i,
        "contenido": doc.page_content[:1000] + ("..." if len(doc.page_content) > 1000 else ""),
        "fuente": Path(doc.metadata.get("source", "Desconocido")).name,
        "pagina": doc.metadata.get("page", 0) + 1,
    } for i, doc in enumerate(docs[:4], start=1)]


def _formatear_historial(historial):
    if not historial:
        return "Sin mensajes anteriores."
    return "\n".join(
        f"{'Alumno' if m['role'] == 'user' else 'Profesor'}: {m['content']}"
        for m in historial[-10:]
        if m.get("role") in {"user", "assistant"}
    )


@st.cache_resource
def _crear_vectorstore(tipo):
    carpeta = BASE_DIR / ("Teoria" if tipo == "temario" else "Labs")
    persistencia = BASE_DIR / ("chroma_temas" if tipo == "temario" else "chroma_practicas")
    if not carpeta.is_dir():
        raise FileNotFoundError(f"No existe la carpeta: {carpeta}")

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    store = Chroma(persist_directory=str(persistencia), embedding_function=embeddings)

    # No duplicar documentos en cada reinicio. Si cambias PDFs después de indexarlos,
    # tendrás que reconstruir su índice (instrucciones debajo).
    if store._collection.count() == 0:
        docs = PyPDFDirectoryLoader(str(carpeta)).load()
        if not docs:
            raise ValueError(f"No hay documentos PDF en {carpeta}")
        for doc in docs:
            nombre = Path(doc.metadata.get("source", "")).stem
            if tipo == "temario":
                doc.metadata["tema"] = nombre
            else:
                doc.metadata["lab"] = nombre
        fragmentos = RecursiveCharacterTextSplitter(chunk_size=5000, chunk_overlap=1000).split_documents(docs)
        store.add_documents(fragmentos)
    return store


@st.cache_resource
def _modelos():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0), ChatOpenAI(model="gpt-4o", temperature=0)


def _crear_retriever(store, practica=None):
    filtro = {"filter": {"lab": practica}} if practica is not None else {}
    mmr = store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 2, "fetch_k": 20, "lambda_mult": 0.8, **filtro},
    )
    similitud = store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 2, **filtro},
    )
    llm_consultas, _ = _modelos()
    multi = MultiQueryRetriever.from_llm(
        retriever=mmr,
        llm=llm_consultas,
        prompt=PromptTemplate.from_template(MULTI_QUERY_PROMPT),
    )
    return EnsembleRetriever(retrievers=[multi, similitud], weights=[0.7, 0.3])


def _consultar(question, tipo, practica=None, historial=None):
    try:
        if tipo == "practicas":
            disponibles = {p.stem for p in (BASE_DIR / "Labs").glob("*.pdf")}
            if practica not in disponibles:
                return "La práctica seleccionada no existe en la carpeta Labs.", []

        store = _crear_vectorstore("temario" if tipo == "temario" else "practicas")
        retriever = _crear_retriever(store, practica if tipo == "practicas" else None)
        docs = retriever.invoke(question)

        # Defensa adicional: evitar que un documento de otra práctica llegue al LLM.
        if tipo == "practicas":
            docs = [doc for doc in docs if doc.metadata.get("lab") == practica]

        if not docs:
            return "No he encontrado fragmentos para responder a esta consulta en los documentos correspondientes.", []

        _, llm_respuestas = _modelos()
        plantilla = RAG_TEMPLATE if tipo == "temario" else RAG_TEMPLATE_PRACTICAS
        prompt = PromptTemplate.from_template(plantilla).format(
            context=_formatear_documentos(docs),
            history=_formatear_historial(historial),
            question=question,
            **({"practica": practica} if tipo == "practicas" else {}),
        )
        respuesta = llm_respuestas.invoke(prompt).content
        return respuesta, _mostrar_documentos(docs)

    except Exception as e:
        print("Ocurrio el siguiente error: {e}")


def query_rag(question, historial=None):
    return _consultar(
        question,
        "teoria",
        historial=historial
    )


def query_rag_labs(question, practica, historial=None):
    return _consultar(
        question,
        "practicas",
        practica=practica,
        historial=historial
    )

