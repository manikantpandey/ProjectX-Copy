import json
import os
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import time

load_dotenv()

file_path = 'extracted_questions.json'

def get_questions_from_json():
    with open(file_path, 'r') as file:
        data = json.load(file)
    if isinstance(data, list):
        return data
    elif 'questions' in data:
        return data['questions']
    else:
        raise ValueError("JSON format is not recognized")

def format_question_for_prompt(question):
    if question['type'] == 'Multiple Choice':
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(question['options'])])
        prompt = f"""Generate a short and simple question with options in a conversational and professional manner for the following question:\n\n{question['question']}\nHere are the options:\n{options_text}\n 
        IMPORTANT: Don't always include the options, include only if options are complex and the user may not aware about the options.
        For example: Age, Gender, Name like this kind of questions are not required the options in the question
        """
    elif question['type'] == 'Checkboxes':
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(question['options'])])
        prompt = f"""Generate a short and simple checkbox question in a conversational and professional manner for the following question:\n\n{question['question']}\nHere are the options:\n{options_text}\n 
        IMPORTANT:  Don't always include the options, include only if options are complex and the user may not aware about the options. Indicate the user they choose multiple options.
        Don't generate inappropriate questions. 
        """
    else:  # Assume short answer or other types
        prompt = f"Generate a short question in a conversational and professional manner for the following question:\n\n{question['question']}\n"
    return prompt

def get_conversation_chain():
    openai_api_key = os.getenv("OPENAI_API_KEY")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, openai_api_key=openai_api_key)
    memory = ConversationBufferMemory()

    chain = ConversationChain(llm=llm, memory=memory, verbose=False)
    return chain

def run_conversation(conversation_chain, questions):
    for question in questions:
        try:
            formatted_prompt = format_question_for_prompt(question)
            generated_question = conversation_chain.predict(input=formatted_prompt)  # Generate the question
            print(generated_question)  # Display the generated question

            user_response = input("Your answer: ")  # Get user's answer
            
            # Validate input based on question type
            if question['type'] == 'multiple choice':
                valid_responses = [str(i+1) for i in range(len(question['options']))]
                if user_response not in valid_responses:
                    print("Invalid choice. Please try again.")
                    continue

            elif question['type'] == 'checkbox':
                valid_responses = set([str(i+1) for i in range(len(question['options']))])
                selected_responses = set(user_response.split(','))
                if not selected_responses.issubset(valid_responses):
                    print("Invalid selections. Please try again.")
                    continue

            # Store or process the response if needed
            print("Thank you for your response.")

        except Exception as e:
            print(f"An error occurred: {e}")
        time.sleep(1)
        print("Great, let's move to the next question.\n")

    print("All form questions have been answered. Thank you for your responses! Ending conversation.")

def main():
    conversation_chain = get_conversation_chain()
    raw_questions = get_questions_from_json()
    run_conversation(conversation_chain, raw_questions)

if __name__ == '__main__':
    main()
