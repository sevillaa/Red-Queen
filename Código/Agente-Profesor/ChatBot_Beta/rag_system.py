from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_classic.retrievers import MultiQueryRetriever, EnsembleRetriever
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import streamlit as st
from prompts import *

@st.cache_resource
def inicializar_sistema_rag():

    carpeta_temario = "C:\\Users\\mario\\TFG\\Código\\Agente-Profesor\\ChatBot_Beta\\Teoria"

    loader = PyPDFDirectoryLoader(carpeta_temario)

    temas = loader.load()

    for doc in temas:
        source = doc.metadata.get("source", "")

        #Obtengo el nombre del PDF
        nombre_pdf = os.path.basename(source)

        #Quito la extension .pdf
        tema = os.path.splitext(nombre_pdf)[0]

        #Guardo el tema como metadata
        doc.metadata["tema"] = tema

    print(f"Se cargaron {len(temas)} temas.")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=5000,
        chunk_overlap=1000
    )

    docs_split = text_splitter.split_documents(temas)

    #Defino el sistema de embebido y donde se va a almacenar
    vectorstore = Chroma.from_documents(
        documents=docs_split,
        embedding=OpenAIEmbeddings(model="text-embedding-3-large"),
        persist_directory="C:\\Users\\mario\\TFG\\chroma_db"
    )

    #Defino los LLMs
    llm_queries = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_generation = ChatOpenAI(model="gpt-4o", temperature=0)

    #Defino el primer retriever (recuperador de info): MMR
    mmr_retriever = vectorstore.as_retriever(
        search_type="mmr", #Técnica que no solo busca recuperar documentos, busca un equilibrio entre relevancia (que sea útil) y diversidad (que no coja documentos que sean copias entre sí)
        search_kwargs={
            "k": 2, #De los 20 recuperados mando 1 al LLM
            "lambda_mult": 0.8, #Cuanto mas cerca a 1 más peso tendrá la relevancia 
            "fetch_k": 20 #Primero recupera los 20 fragmentos candidatos
        }
    )

    similarity_retriever = vectorstore.as_retriever(
        search_type="similarity", #Otro sistema de retriever que lo que hace es recuperar los fragmentos más similares
        search_kwargs={
            "k": 2,#En este caso recupera los 2 más similares
        } 
    )


    multi_query_prompt = PromptTemplate.from_template(MULTI_QUERY_PROMPT)

    # MultiQueryRetriever con prompt personalizado
    mmr_multi_retriever = MultiQueryRetriever.from_llm(
        retriever=mmr_retriever,
        llm=llm_queries,
        prompt=multi_query_prompt
    )

    # Ensemble Retriever que combina mmr y similarity
    ensemble_retriever = EnsembleRetriever(
        retrievers = [mmr_multi_retriever, similarity_retriever],
        weights=[0.7, 0.3], # Mayor peso a mmr
        similarity_threshold=0.7
    )

    prompt = PromptTemplate.from_template(RAG_TEMPLATE) #Transforma el prompt en una plantilla ya que tiene variables que el llm tendrá que procesar

    # Función para formatear y preprocesar los documentos recuperados
    def format_doc(docs):
        formatted = []

        '''Con esto lo que hago es que en cada fragmento meto metadatos como el número de fragmento, la fuente y la página. Para a la hora de recuperar datos que involucren distintos fragmentos el LLM sepa que fragmentos pertenecen a la misma página'''
        for i, doc in enumerate(docs):
            header = f"[Fragmento {i}]" #Para que el LLM diferencie entre fragmentos
            if doc.metadata:
                if 'source' in doc.metadata:
                    source = doc.metadata['source'].split("\\")[-1] if '\\' in doc.metadata['source'] else doc.metadata['source'] #El nombre del documento
                    header += f" - Fuente: {source}"
                if 'page' in doc.metadata:
                    header += f" - Pagina: {doc.metadata['page']}"
                if 'tema' in doc.metadata:
                    header += f" - Tema: {doc.metadata['tema']}"

            content = doc.page_content.strip()
            formatted.append(f"{header}\n{content}") #De esta forma formateo los fragmentos con una cabecera que incluye metadatos para relacionarlos y el propio contenido del fragmento

        return "\n\n".join(formatted)

    rag_chain = (
        {
            "context": ensemble_retriever | format_doc,
            "question": RunnablePassthrough() #Indico que este argumento ya se lo pasaré
        }
        | prompt
        | llm_generation
        | StrOutputParser() #Procesa lo que devuelve el LLM
    )

    return rag_chain, mmr_multi_retriever

def query_rag(question):
    try:
        rag_chain, retriever = inicializar_sistema_rag()

        #Obtener la respuesta
        response = rag_chain.invoke(question)

        #Obetener los fragmentos para mostrarlos
        docs = retriever.invoke(question)

        # Formatear los fragmentos para mostrar
        docs_info = []
        for i, doc in enumerate(docs[:2], 1): #Solamente los k primeros que hemos pedido que nos devuelva
            doc_info = {
                "fragmento": i,
                "contenido": doc.page_content[:1000] + "..." if len(doc.page_content) > 1000 else doc.page_content,
                "fuente": doc.metadata.get('source', 'No especificada').split("\\"[-1]),
                "pagina": doc.metadata.get('page', 'No especificada')
            }

            docs_info.append(doc_info)

        return response, docs_info
    except Exception as e:
        error_msg = f"Error al procesar la consulta: {str(e)}"
        return error_msg, []




