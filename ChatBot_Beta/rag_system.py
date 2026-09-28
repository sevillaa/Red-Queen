from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_classic.retrievers import MultiQueryRetriever, EnsembleRetriever
import streamlit as st

@st.cache_resource
def inicializar_sistema_rag():

    #Defino el sistema de embebido y donde se va a almacenar
    vectorstore = Chroma(
        embedding_function=OpenAIEmbeddings(model="text-embedding-3-large"),
        persist_directory="C:\\Users\\mario\\TFG\\chroma_db"
    )

    #Defino los LLMs
    llm_queries = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_generation = ChatOpenAI(model="gpt-4o", temperature=0)

    #Defino el primer retriever (recuperador de info): MMR

