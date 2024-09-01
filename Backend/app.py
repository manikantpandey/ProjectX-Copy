import streamlit as st
import requests
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
# from langchain_community.llms import OpenAI
from langchain_openai import OpenAI
import time
import pandas as pd
from datetime import datetime

def get_form_questions(form_url):
    with st.spinner("Fetching data from Google Form..."):
        response = requests.post("http://localhost:5002/fetch_google_form", json={"url": form_url})
        if response.status_code == 200:
            time.sleep(2)  
            return response.json()["questions"]
        else:
            st.error("Unable to fetch form questions. Please verify the URL and try again.")
            return None

def get_conversation_chain():
    openai_api_key = "sk-proj-28Ujki6MQfU3PUXE40lCT3BlbkFJXljkLHDYJwGmGmrjCByX"
    llm = OpenAI(temperature=0.7, openai_api_key=openai_api_key)
    memory = ConversationBufferMemory()
    conversation_chain = ConversationChain(llm=llm, memory=memory, verbose=False)
    return conversation_chain

def format_question(question):
    if isinstance(question, dict):
        question_text = question.get("question", "")
        options = question.get("options", [])
        if options:
            options_text = ", ".join(options)
            return f"{question_text}\nOptions: {options_text}"
        return question_text
    return "Unable to format question"

def get_ai_response(user_input, current_question):
    formatted_question = format_question(current_question)
    prompt = f"""
    You are a friendly and empathetic customer service representative. Your task is to gather information for a form while maintaining a natural conversation. 
    The user's last response was: "{user_input}"
    The next question you need to ask is: "{formatted_question}"
    Respond to the user's input if relevant, then ask the next question exactly as it is formatted, including any options if present. Keep your response concise and friendly. Don't add any unnecessary questions or information.
    """
    response = st.session_state.conversation.predict(input=prompt)
    return response

def save_conversation_to_excel(conversation_data):
    df = pd.DataFrame(conversation_data, columns=[
        "Conversation ID", "Question asked by Bot", "User Response", 
        "Endpoint created by GPT", "Model Name", "Function Name", "Temperature", 
        "Top_p", "Tool Choice", "Latency (s)"
    ])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"conversation_{timestamp}.xlsx"
    df.to_excel(filename, index=False)
    return filename

def main():
    st.set_page_config(page_title="Customer Service Assistant", page_icon=":telephone_receiver:", layout="wide")
    
    if "conversation" not in st.session_state:
        st.session_state.conversation = get_conversation_chain()
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "form_questions" not in st.session_state:
        st.session_state.form_questions = None
    if "current_question_index" not in st.session_state:
        st.session_state.current_question_index = 0
    if "loading_form" not in st.session_state:
        st.session_state.loading_form = False
    if "conversation_data" not in st.session_state:
        st.session_state.conversation_data = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = 1
    if "last_bot_question" not in st.session_state:
        st.session_state.last_bot_question = ""

    st.title("Customer Service Assistant")

    with st.sidebar:
        st.header("Form Setup")
        form_url = st.text_input("Enter the Google Form URL:")
        if st.button("Load Form"):
            st.session_state.loading_form = True
            st.session_state.form_questions = get_form_questions(form_url)
            st.session_state.loading_form = False
            if st.session_state.form_questions:
                st.success("Form loaded successfully!")
                st.session_state.current_question_index = 0
                st.session_state.chat_history = []
                initial_message = "Hi there! I'm here to help you with some questions. How are you doing today?"
                st.session_state.chat_history.append(("Agent", initial_message))
                st.session_state.last_bot_question = initial_message

        if st.session_state.form_questions:
            st.subheader("Form Questions")
            for i, question in enumerate(st.session_state.form_questions):
                st.write(f"{i+1}. {format_question(question)}")

    if st.session_state.loading_form:
        st.info("Fetching and processing data from Google Form. Please wait...")

    if st.session_state.form_questions:
        chat_container = st.container()
        
        with chat_container:
            for speaker, message in st.session_state.chat_history:
                if speaker == "Human":
                    st.write(f"You: {message}")
                else:
                    st.write(f"Agent: {message}")

        st.write("<div style='padding: 180px 0px;'></div>", unsafe_allow_html=True)

        with st.form(key='user_input_form', clear_on_submit=True):
            user_input = st.text_input("Your response:", key="user_input")
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                submit_button = st.form_submit_button("Send")
            with col2:
                start_over_button = st.form_submit_button("Start Over")
            with col3:
                clear_chat_button = st.form_submit_button("Clear Chat")

        if submit_button and user_input:
            start_time = time.time()
            
            st.session_state.chat_history.append(("Human", user_input))
            
            if st.session_state.current_question_index < len(st.session_state.form_questions):
                current_question = st.session_state.form_questions[st.session_state.current_question_index]
                response = get_ai_response(user_input, current_question)
                st.session_state.chat_history.append(("Agent", response))
                st.session_state.current_question_index += 1
            else:
                final_response = st.session_state.conversation.predict(input=f"The user said: '{user_input}'. All form questions have been answered. Provide a friendly closing statement.")
                response = final_response
                st.session_state.chat_history.append(("Agent", response))
            
            end_time = time.time()
            latency = end_time - start_time

            st.session_state.conversation_data.append([
                st.session_state.conversation_id,
                st.session_state.last_bot_question,
                user_input,
                "N/A",  # Endpoint created by GPT
                "gpt-3.5-turbo",  # Assuming this is the model used
                "get_ai_response",
                0.7,  # Temperature
                1.0,  # Top_p (assuming default value)
                "auto",  # Tool Choice
                latency
            ])

            st.session_state.conversation_id += 1
            st.session_state.last_bot_question = response
            
            st.rerun()

        if start_over_button:
            st.session_state.current_question_index = 0
            st.session_state.chat_history = []
            initial_message = "Let's start over. How can I assist you today?"
            st.session_state.chat_history.append(("Agent", initial_message))
            st.session_state.last_bot_question = initial_message
            st.rerun()

        if clear_chat_button:
            st.session_state.chat_history = []
            st.session_state.last_bot_question = ""
            st.rerun()

        if st.button("Save Conversation"):
            if st.session_state.conversation_data:
                filename = save_conversation_to_excel(st.session_state.conversation_data)
                st.success(f"Conversation saved to {filename}")
            else:
                st.warning("No conversation data to save.")

if __name__ == '__main__':
    main()